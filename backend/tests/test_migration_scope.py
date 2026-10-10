from sqlalchemy import Column, ForeignKey, Index, Integer, MetaData, Table

from app.db.migration_scope import include_object


def test_retired_objects_are_protected_but_other_schema_drift_is_visible() -> None:
    metadata = MetaData()
    jobs = Table("job_runs", metadata, Column("id", Integer, primary_key=True))
    sources = Table(
        "sources", metadata, Column("schedule_seconds", Integer), Column("next_check_at", Integer)
    )
    fetches = Table(
        "source_fetches", metadata, Column("job_run_id", Integer, ForeignKey("job_runs.id"))
    )
    due = Index("ix_sources_due_active", sources.c.next_check_at)
    assert not include_object(jobs, jobs.name, "table", True, None)
    assert not include_object(sources.c.schedule_seconds, "schedule_seconds", "column", True, None)
    assert not include_object(due, due.name, "index", True, None)
    foreign_key = next(iter(fetches.foreign_key_constraints))
    assert not include_object(foreign_key, foreign_key.name, "foreign_key_constraint", True, None)
    assert include_object(sources, sources.name, "table", True, None)
    assert include_object(None, "unrelated_table", "table", True, None)
    assert include_object(None, "new_column", "column", True, None)
    assert include_object(jobs, jobs.name, "table", True, jobs)
    assert include_object(jobs, jobs.name, "table", False, None)
