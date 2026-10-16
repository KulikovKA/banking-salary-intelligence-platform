"""Launch the isolated live experiment; credentials stay in child process environments."""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx2 as httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument(
        "--documents",
        type=Path,
        help="Prepared knowledge package; defaults to inventory's sibling manifest",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    # Deliberately load just the provider key; do not import production/DB configuration.
    values = {}
    for line in args.env_file.read_text(encoding="utf-8-sig").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            values[key.strip()] = value.strip().strip('"').strip("'")
    key = env.get("GROQ_API_KEY") or env.get("LLM_API_KEY")
    key = key or values.get("GROQ_API_KEY") or values.get("LLM_API_KEY")
    if not key:
        parser.error("GROQ_API_KEY or LLM_API_KEY is required (value is never printed)")
    if not args.inventory.is_file():
        parser.error("Local inventory file is missing")
    env.update(
        {
            "LLM_API_KEY": key,
            "LIVE_DEMO_ENABLED": "true",
            "APP_ENV": "poc",
            "LIVE_DEMO_TOKEN": secrets.token_urlsafe(32),
            "LIVE_DEMO_INVENTORY": str(args.inventory.resolve()),
            "NEXT_TELEMETRY_DISABLED": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    documents = args.documents or args.inventory.resolve().parent
    if args.documents or (documents / "manifest.json").is_file():
        env["LIVE_DEMO_DOCUMENTS"] = str(documents.resolve())
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        parser.error("npm is required")
    logs = root / ".local" / "live-demo"
    logs.mkdir(parents=True, exist_ok=True)
    children: list[subprocess.Popen[bytes]] = []
    try:
        for name, command, cwd in (
            (
                "backend",
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.local_demo:create_app",
                    "--factory",
                    "--app-dir",
                    "backend",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8010",
                    "--no-proxy-headers",
                    "--no-access-log",
                ],
                root,
            ),
            (
                "frontend",
                [npm, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3010"],
                root / "frontend",
            ),
        ):
            with (logs / f"{name}.log").open("ab") as output:
                child_env = env.copy()
                if name == "frontend":
                    child_env.pop("LLM_API_KEY", None)
                    child_env.pop("GROQ_API_KEY", None)
                child = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=child_env,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            children.append(child)
            if name == "backend":
                # Parsing originals takes time; never expose a chat before API startup completes.
                deadline = time.monotonic() + 90
                with httpx.Client(timeout=2, trust_env=False) as client:
                    while time.monotonic() < deadline and child.poll() is None:
                        try:
                            ready = client.get(
                                "http://127.0.0.1:8010/local-demo/status",
                                headers={
                                    "X-Live-Demo-Token": env["LIVE_DEMO_TOKEN"],
                                },
                            )
                            if ready.status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.5)
                    else:
                        raise SystemExit("Local parser/API startup failed; inspect backend.log")
        print("Live Groq chat: http://127.0.0.1:3010", flush=True)
        print("Enable public-text processing with the checkbox. Logs: .local/live-demo", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(1)
        raise SystemExit("A demo process stopped; inspect .local/live-demo/*.log")
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            elif child.poll() is None:
                child.terminate()


if __name__ == "__main__":
    main()
