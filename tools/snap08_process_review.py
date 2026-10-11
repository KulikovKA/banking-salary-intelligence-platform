"""Controlled Linux runner lifecycle probe (no bank or provider networking)."""

import json
import os
import signal
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from app.contracts.parsing import ParseRequest
from app.parsing import runner


def alive(pid: int) -> bool:
    path = Path(f"/proc/{pid}/stat")
    return path.exists() and path.read_text().split()[2] != "Z"


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    original = root / "original.html"
    original.write_text("synthetic")
    request = ParseRequest(
        source_version_id=uuid4(), raw_sha256="0" * 64, kind="html",
        corpus_kind="synthetic", parser_version="review-probe",
    )
    for mode in ("timeout", "success", "crash"):
        pid_file = root / f"{mode}.pid"
        runner._WORKER_BOOTSTRAP = f'''
import json, subprocess, sys, time
request = json.loads(sys.stdin.buffer.read())
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
open({str(pid_file)!r}, "w").write(str(child.pid))
if {mode!r} == "timeout":
    time.sleep(20)
elif {mode!r} == "crash":
    sys.exit(2)
else:
    output = {{"status": "ok", "parser_version": request["parser_version"],
              "extraction_sha256": "0" * 64}}
    open(sys.argv[3], "w").write(json.dumps(output))
'''
        outcome = "ok"
        try:
            runner.run_bounded_parse(request, original, timeout_seconds=1)
        except runner.BoundedParseError as exc:
            outcome = exc.code
        pid = int(pid_file.read_text())
        time.sleep(0.1)
        print(json.dumps({"mode": mode, "outcome": outcome, "descendant_alive": alive(pid)}))
        leaked = alive(pid)
        if leaked:
            os.kill(pid, signal.SIGKILL)
        assert not leaked, f"live descendant after {mode}"
