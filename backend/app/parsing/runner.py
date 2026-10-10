"""Run the built-in document parsers in a bounded local Python subprocess.

The parent accepts only a :class:`ParseRequest` and an existing local path. It
does not resolve URLs or perform network I/O. The child runs with a minimal
environment, Python-level socket calls disabled, bounded JSON IPC, and platform
resource limits where the operating system exposes them.

Linux enforces address-space, CPU-time, file-size, open-file and core-dump
limits with ``resource.setrlimit``. Windows enforces per-process memory and
kill-on-close termination with a Job Object. Both platforms enforce a
wall-clock timeout in the parent and forcibly terminate the child on expiry. Python-level
socket blocking is defense in depth, not an OS network sandbox: both processes
run as the caller, so this module does not restrict arbitrary filesystem access
or native-code network access. The parser implementations themselves are the
trusted, offline code boundary.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from app.contracts.parsing import ParseRequest, ParseResult

DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_OUTPUT_BYTES = 32 * 1024 * 1024
_MAX_REQUEST_BYTES = 64 * 1024
_MIN_OUTPUT_BYTES = 1024


class BoundedParseError(RuntimeError):
    """Base exception for safe runner failures; ``code`` is stable for callers."""

    code = "BOUNDED_PARSE_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class InvalidParseRequest(BoundedParseError):
    """The DTO, local original path, or caller-supplied limits are invalid."""

    code = "INVALID_PARSE_REQUEST"


class BoundedParseTimeout(BoundedParseError):
    """The child exceeded its wall-clock limit and was terminated."""

    code = "PARSE_TIMEOUT"


class BoundedParseCrash(BoundedParseError):
    """The child exited unsuccessfully before producing a valid result."""

    code = "PARSE_WORKER_CRASH"


class BoundedParseOutputError(BoundedParseError):
    """The child result exceeded the IPC bound or failed DTO validation."""

    code = "PARSE_INVALID_OUTPUT"


class BoundedParseResourceError(BoundedParseError):
    """The platform could not apply a requested hard resource limit."""

    code = "PARSE_RESOURCE_LIMIT_UNAVAILABLE"


_WORKER_BOOTSTRAP = r'''
import json
import math
import os
import sys

kind, original_path, result_path = sys.argv[1:4]
max_output_bytes = int(sys.argv[4])
memory_limit_bytes = int(sys.argv[5])
cpu_limit_seconds = int(sys.argv[6])
request_bytes = sys.stdin.buffer.read(65537)
if len(request_bytes) > 65536:
    raise SystemExit(64)

if os.name == "posix":
    import resource
    infinity = resource.RLIM_INFINITY
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit_seconds, cpu_limit_seconds + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (max_output_bytes, max_output_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

# These parsers need no sockets. This blocks accidental Python-level networking;
# it is not a replacement for an OS sandbox against native extensions.
import socket
def _network_disabled(*args, **kwargs):
    raise OSError("PARSER_NETWORK_DISABLED")
socket.socket = _network_disabled
socket.create_connection = _network_disabled
socket.socketpair = _network_disabled

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
from app.contracts.parsing import ParseRequest
from app.parsing.pdf import PdfParser
from app.parsing.xlsx import XlsxParser
from app.parsing.html import HtmlParser

request = ParseRequest.model_validate_json(request_bytes)
parser = {"pdf": PdfParser, "xlsx": XlsxParser, "html": HtmlParser}[kind]()
result = parser.parse(request, original_path)
payload = result.model_dump_json().encode("utf-8")
if len(payload) > max_output_bytes:
    raise SystemExit(73)
with open(result_path, "xb") as output:
    output.write(payload)
'''.lstrip()


def run_bounded_parse(
    request: ParseRequest,
    original_path: str | os.PathLike[str],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> ParseResult:
    """Run a built-in parser against an already verified local original.

    Args:
        request: Frozen parser input DTO; its ``kind`` selects PDF, XLSX, or HTML.
        original_path: Path to the stored original. URLs and non-file paths are
            rejected; the parser also verifies the request's SHA-256.
        timeout_seconds: Maximum wall-clock time before the worker is killed.
        memory_limit_bytes: Hard per-process memory/address-space cap on Linux
            and Windows. Other platforms report that the limit is unavailable.
        max_output_bytes: Maximum serialized ``ParseResult`` size over IPC.

    Returns:
        A validated ``ParseResult`` preserving parser DTO fields verbatim.

    Raises:
        InvalidParseRequest: Input DTO, original path, or limit is invalid.
        BoundedParseTimeout: The worker exceeded its wall-clock limit.
        BoundedParseCrash: The worker exited without a successful result.
        BoundedParseOutputError: Output was too large, malformed, or invalid.
        BoundedParseResourceError: A hard platform resource limit could not be
            established. Linux and Windows are supported; other OSes are not.
    """
    if not isinstance(request, ParseRequest):
        raise InvalidParseRequest("request must be a ParseRequest")
    if request.kind not in {"pdf", "xlsx", "html"}:
        raise InvalidParseRequest("unsupported parser kind")
    _validate_limits(timeout_seconds, memory_limit_bytes, max_output_bytes)
    try:
        path = Path(original_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise InvalidParseRequest("original_path must identify an existing local file") from exc
    if not path.is_file():
        raise InvalidParseRequest("original_path must identify an existing local file")

    request_bytes = request.model_dump_json().encode("utf-8")
    if len(request_bytes) > _MAX_REQUEST_BYTES:
        raise InvalidParseRequest("serialized ParseRequest exceeds IPC limit")
    backend_dir = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="bsi-parse-") as temp_dir:
        worker_path = Path(temp_dir) / "worker.py"
        result_path = Path(temp_dir) / "result.json"
        worker_path.write_text(_WORKER_BOOTSTRAP, encoding="utf-8")
        worker_args = [
            sys.executable,
            "-I",
            str(worker_path),
            request.kind,
            str(path),
            str(result_path),
            str(max_output_bytes),
            str(memory_limit_bytes),
            str(max(1, math.ceil(timeout_seconds))),
        ]
        process: subprocess.Popen[bytes] | None = None
        job_handle: int | None = None
        try:
            process = subprocess.Popen(
                worker_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=backend_dir.parent,
                env=_minimal_environment(),
                shell=False,
                close_fds=True,
                start_new_session=(os.name == "posix"),
                creationflags=(
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    if os.name == "nt"
                    else 0
                ),
            )
            if os.name == "nt":
                job_handle = _attach_windows_job(process, memory_limit_bytes)
            elif os.name != "posix":
                raise BoundedParseResourceError(
                    "hard resource limits are supported only on Linux and Windows"
                )
            try:
                process.communicate(input=request_bytes, timeout=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                _terminate_process(process, job_handle)
                job_handle = None
                raise BoundedParseTimeout() from exc

            if process.returncode != 0:
                if process.returncode == 73:
                    raise BoundedParseOutputError("worker result exceeds max_output_bytes")
                raise BoundedParseCrash(f"worker exited with code {process.returncode}")
            try:
                output_size = result_path.stat().st_size
                if output_size > max_output_bytes:
                    raise BoundedParseOutputError("worker result exceeds max_output_bytes")
                output = result_path.read_bytes()
            except FileNotFoundError as exc:
                raise BoundedParseCrash("worker exited without a result") from exc
            if len(output) != output_size or len(output) > max_output_bytes:
                raise BoundedParseOutputError("worker result size is invalid")
            try:
                result = ParseResult.model_validate_json(output)
            except (ValidationError, ValueError, UnicodeDecodeError) as exc:
                raise BoundedParseOutputError("worker returned an invalid ParseResult") from exc
            if result.parser_version != request.parser_version:
                raise BoundedParseOutputError("worker changed parser_version")
            return result
        except BoundedParseError:
            if process is not None and process.poll() is None:
                _terminate_process(process, job_handle)
                job_handle = None
            raise
        except (OSError, subprocess.SubprocessError) as exc:
            if process is not None and process.poll() is None:
                _terminate_process(process, job_handle)
                job_handle = None
            raise BoundedParseCrash("could not complete parser worker") from exc
        finally:
            if job_handle is not None:
                _close_windows_handle(job_handle)
            if process is not None and process.poll() is None:
                _terminate_process(process, job_handle)


def _validate_limits(timeout: float, memory: int, output: int) -> None:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise InvalidParseRequest("timeout_seconds must be a finite positive number")
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 86_400:
        raise InvalidParseRequest("timeout_seconds must be in (0, 86400]")
    if isinstance(memory, bool) or not isinstance(memory, int) or memory < 64 * 1024 * 1024:
        raise InvalidParseRequest("memory_limit_bytes must be an integer of at least 64 MiB")
    if isinstance(output, bool) or not isinstance(output, int):
        raise InvalidParseRequest("max_output_bytes must be an integer")
    if not _MIN_OUTPUT_BYTES <= output <= 256 * 1024 * 1024:
        raise InvalidParseRequest("max_output_bytes must be between 1 KiB and 256 MiB")


def _minimal_environment() -> dict[str, str]:
    allowed = {"PATH", "LANG", "LC_ALL", "TZ", "TMP", "TEMP", "TMPDIR"}
    if os.name == "nt":
        allowed.update({"SYSTEMROOT", "WINDIR", "PATHEXT"})
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def _terminate_process(process: subprocess.Popen[bytes], job_handle: int | None) -> None:
    if job_handle is not None:
        _close_windows_handle(job_handle)
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    if os.name == "posix" and process.poll() is None:
        try:
            os.killpg(process.pid, 9)  # type: ignore[attr-defined]
        except OSError:
            pass
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def _close_windows_handle(handle: int) -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle(handle)


def _attach_windows_job(
    process: subprocess.Popen[bytes], memory_limit_bytes: int
) -> int:
    """Apply a Windows Job Object memory, process-count, and kill-on-close limit."""
    import ctypes
    from ctypes import wintypes

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise BoundedParseResourceError("could not create Windows Job Object")
    limits = ExtendedLimitInformation()
    # JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    limits.BasicLimitInformation.LimitFlags = 0x0100 | 0x2000
    limits.ProcessMemoryLimit = memory_limit_bytes
    ok = kernel32.SetInformationJobObject(
        handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
    )
    process_handle = int(process._handle)  # type: ignore[attr-defined]
    if not ok or not kernel32.AssignProcessToJobObject(handle, process_handle):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)
        raise BoundedParseResourceError(f"could not apply Windows Job Object limits ({error})")
    return int(handle)
