"""Validate standalone main documentation, snapshot prompts and source decisions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]\n]*\]\(([^\s)]+)\)")


def validate() -> list[str]:
    errors: list[str] = []
    markdown = [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md")]
    for path in markdown:
        body = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for href in LINK.findall(body):
            if urlsplit(href).scheme or href.startswith("#"):
                continue
            destination = (path.parent / unquote(href.split("#", 1)[0])).resolve()
            if not destination.exists():
                errors.append(f"{path.relative_to(ROOT)}: missing link {href}")

    registry = json.loads((ROOT / "docs/implementation/TASKS.json").read_text(encoding="utf-8"))
    tasks = registry["tasks"]
    ids = [task["id"] for task in tasks]
    if ids != [f"SNAP-{number:02}" for number in range(1, len(tasks) + 1)]:
        errors.append("TASKS.json: IDs must be unique and sequential")
    by_id = {task["id"]: task for task in tasks}
    plan = (ROOT / "docs/implementation/MASTER_PLAN.md").read_text(encoding="utf-8")
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id not in by_id:
            errors.append(f"Unknown dependency: {task_id}")
            return
        if task_id in visiting:
            errors.append(f"Dependency cycle: {task_id}")
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in by_id[task_id]["deps"]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task in tasks:
        visit(task["id"])
        fields = ("title", "owned_paths", "outcome", "implementation", "acceptance", "parallelism")
        for field in fields:
            if not task.get(field):
                errors.append(f"{task['id']}: missing {field}")
        prompt = ROOT / "docs/implementation" / task["prompt"]
        if not prompt.is_file():
            errors.append(f"{task['id']}: missing prompt")
            continue
        text = prompt.read_text(encoding="utf-8")
        for value in (task["id"], task["reasoning_effort"], task["outcome"], *task["deps"]):
            if value not in text:
                errors.append(f"{task['id']}: prompt mismatch {value}")
        dependencies = ", ".join(task["deps"]) or "—"
        row = (
            f"| [{task['id']}]({task['prompt']}) | {task['title']} | {dependencies} | "
            f"{task['reasoning_effort']} | {task['status']} |"
        )
        if row not in plan:
            errors.append(f"{task['id']}: plan/registry row mismatch")
        if task["status"] not in {"TODO", "IN_PROGRESS", "DONE", "BLOCKED"}:
            errors.append(f"{task['id']}: invalid status")

    if len(tasks) != 19:
        errors.append("Snapshot v1 requires exactly 19 prompts")
    if (ROOT / "docs/archive").exists():
        errors.append("Historical documentation belongs to the archive branch, not main")
    if (ROOT / "backend/app/ingestion/jobs.py").exists():
        errors.append("Runtime queue helper must not be present in operator-only main")
    manifest = json.loads(
        (ROOT / "tests/fixtures/manifests/sources.json").read_text(encoding="utf-8")
    )
    if manifest["snapshot_context"]["gates"] != {
        "G1": "NOT_PASSED", "G2": "NOT_PASSED", "S1": "BLOCKED"
    }:
        errors.append("Source manifest gates require a reviewed change with evidence")
    if set(bank["bank_code"] for bank in manifest["banks"]) != {
        "sber", "vtb", "alfa", "kuban_credit"
    }:
        errors.append("Source manifest must describe all four banks")
    for task in tasks:
        text = (ROOT / "docs/implementation" / task["prompt"]).read_text(encoding="utf-8")
        for field in ("implementation", "acceptance", "parallelism", "outcome"):
            if task[field] not in text:
                errors.append(f"{task['id']}: prompt/registry {field} mismatch")
    return errors


def main() -> int:
    errors = validate()
    for error in errors:
        print(error)
    if errors:
        print(f"FAIL: {len(errors)} documentation errors")
        return 1
    print("PASS: standalone main links, 19 snapshot prompts, DAG/statuses and source decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
