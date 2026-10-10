"""Protect retired physical audit data outside the active ORM/autogenerate scope.

Original migrations remain immutable. Only explicitly retired objects absent
from application metadata are protected from destructive autogeneration.
Nothing here dispatches work or maps a runtime queue.
"""

from typing import Any

RETIRED_COLUMNS = {
    "sources": {"schedule_seconds", "next_check_at"},
    "source_fetches": {"job_run_id"},
}
RETIRED_INDEXES = {"ix_sources_due_active", "ix_source_fetches_job_run_id"}


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    if not reflected or compare_to is not None:
        return True
    if type_ == "table":
        return name != "job_runs"
    table = getattr(obj, "table", None)
    retired = RETIRED_COLUMNS.get(getattr(table, "name", ""), set())
    if type_ == "column":
        return name not in retired
    if type_ == "index":
        return name not in RETIRED_INDEXES
    if type_ == "foreign_key_constraint":
        return not any(column.name in retired for column in obj.columns)
    return True
