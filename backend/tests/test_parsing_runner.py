"""Process isolation and bounded IPC checks for the local parser runner."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from uuid import uuid4

import pytest

from app.contracts.parsing import ParseRequest
from app.parsing import runner
from app.parsing.runner import (
    BoundedParseCrash,
    BoundedParseOutputError,
    BoundedParseResourceError,
    BoundedParseTimeout,
    run_bounded_parse,
)


def _request(path: Path) -> ParseRequest:
    return ParseRequest(
        source_version_id=uuid4(),
        raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        kind="html",
        corpus_kind="synthetic",
        parser_version="runner-test",
    )


def _alive_non_zombie(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit_code = kernel32.GetExitCodeProcess
        get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        handle = open_process(0x1000, False, pid)
        if not handle:
            return False
        exit_code = wintypes.DWORD()
        try:
            return bool(get_exit_code(handle, ctypes.byref(exit_code))) and exit_code.value == 259
        finally:
            close_handle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat_path = Path(f"/proc/{pid}/stat")
    if stat_path.exists():
        try:
            fields = stat_path.read_text(encoding="ascii").split()
        except FileNotFoundError:
            # The process can exit after exists() succeeds but before the
            # procfs file is opened. Treat that race as an exited process.
            return False
        return len(fields) < 3 or fields[2] != "Z"
    return True


@pytest.mark.skipif(
    not (os.name == "posix" and runner.sys.platform.startswith("linux")),
    reason="/proc process state is Linux-specific",
)
def test_alive_non_zombie_handles_procfs_exit_race(monkeypatch) -> None:
    monkeypatch.setattr(os, "kill", lambda _pid, _signal: None)
    monkeypatch.setattr(Path, "exists", lambda _path: True)

    def read_disappeared_stat(_path, *args, **kwargs):
        raise FileNotFoundError("process exited before procfs read")

    monkeypatch.setattr(Path, "read_text", read_disappeared_stat)

    assert not _alive_non_zombie(12345)


def test_worker_environment_excludes_application_secrets(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("GROQ_API_KEY", "secret-token")
    monkeypatch.setenv("SNAP08_PRIVATE_VALUE", "private")

    environment = runner._minimal_environment()

    assert "DATABASE_URL" not in environment
    assert "GROQ_API_KEY" not in environment
    assert "SNAP08_PRIVATE_VALUE" not in environment
    assert set(environment) <= {
        "PATH", "LANG", "LC_ALL", "TZ", "TMP", "TEMP", "TMPDIR",
        "SYSTEMROOT", "WINDIR", "PATHEXT",
    }


def test_unsupported_platform_fails_before_opening_original(tmp_path, monkeypatch) -> None:
    original = tmp_path / "not-read.html"
    request = ParseRequest(
        source_version_id=uuid4(),
        raw_sha256="0" * 64,
        kind="html",
        corpus_kind="synthetic",
        parser_version="runner-test",
    )
    monkeypatch.setattr(runner.os, "name", "posix")
    monkeypatch.setattr(runner.sys, "platform", "darwin")

    with pytest.raises(BoundedParseResourceError):
        run_bounded_parse(request, original)


def test_worker_output_limit_returns_stable_error(tmp_path, monkeypatch) -> None:
    original = tmp_path / "input.html"
    original.write_text("<html><body>synthetic</body></html>", encoding="utf-8")
    bootstrap = runner._WORKER_BOOTSTRAP
    target = 'payload = result.model_dump_json().encode("utf-8")'
    assert target in bootstrap
    monkeypatch.setattr(
        runner,
        "_WORKER_BOOTSTRAP",
        bootstrap.replace(target, "payload = b'x' * (max_output_bytes + 1)"),
    )

    with pytest.raises(BoundedParseOutputError):
        run_bounded_parse(_request(original), original, max_output_bytes=1024)


@pytest.mark.skipif(
    not (os.name == "nt" or (os.name == "posix" and runner.sys.platform.startswith("linux"))),
    reason="process-group and Windows Job Object termination are platform-specific",
)
def test_timeout_terminates_worker_and_descendant(tmp_path, monkeypatch) -> None:
    original = tmp_path / "input.html"
    original.write_text("<html><body>synthetic</body></html>", encoding="utf-8")
    pid_file = tmp_path / "child.pid"
    bootstrap = runner._WORKER_BOOTSTRAP
    target = "request = ParseRequest.model_validate_json(request_bytes)"
    assert target in bootstrap
    injected = (
        target
        + "\nimport subprocess, time\n"
        + 'child = subprocess.Popen([sys.executable, "-c", '
        + '"import time; time.sleep(30)"])\n'
        + f"open({str(pid_file)!r}, 'w', encoding='ascii').write(str(child.pid))\n"
        + "time.sleep(30)"
    )
    monkeypatch.setattr(runner, "_WORKER_BOOTSTRAP", bootstrap.replace(target, injected))

    with pytest.raises(BoundedParseTimeout):
        run_bounded_parse(_request(original), original, timeout_seconds=1.5)

    assert pid_file.exists()
    child_pid = int(pid_file.read_text(encoding="ascii"))
    deadline = time.monotonic() + 5
    while _alive_non_zombie(child_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive_non_zombie(child_pid)


@pytest.mark.parametrize("crash", [False, True])
@pytest.mark.skipif(
    not (os.name == "nt" or (os.name == "posix" and runner.sys.platform.startswith("linux"))),
    reason="process-group and Windows Job Object termination are platform-specific",
)
def test_completed_worker_also_terminates_descendants(tmp_path, monkeypatch, crash) -> None:
    original = tmp_path / "input.html"
    original.write_text("<html><body><p>synthetic</p></body></html>", encoding="utf-8")
    pid_file = tmp_path / "completed-child.pid"
    target = "request = ParseRequest.model_validate_json(request_bytes)"
    injected = (
        target
        + "\nimport subprocess\n"
        + 'child = subprocess.Popen([sys.executable, "-c", '
        + '"import time; time.sleep(30)"])\n'
        + f"open({str(pid_file)!r}, 'w', encoding='ascii').write(str(child.pid))\n"
        + ("raise SystemExit(2)\n" if crash else "")
    )
    monkeypatch.setattr(
        runner, "_WORKER_BOOTSTRAP", runner._WORKER_BOOTSTRAP.replace(target, injected)
    )
    try:
        if crash:
            with pytest.raises(BoundedParseCrash):
                run_bounded_parse(_request(original), original)
        else:
            assert run_bounded_parse(_request(original), original).status == "ok"
        assert pid_file.exists()
        child_pid = int(pid_file.read_text(encoding="ascii"))
        deadline = time.monotonic() + 5
        while _alive_non_zombie(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _alive_non_zombie(child_pid)
    finally:
        if pid_file.exists():
            child_pid = int(pid_file.read_text(encoding="ascii"))
            if _alive_non_zombie(child_pid):
                import signal

                os.kill(child_pid, getattr(signal, "SIGKILL", signal.SIGTERM))
