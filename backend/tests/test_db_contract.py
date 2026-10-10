import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app.auth import models as auth_models  # noqa: F401
from app.corpus import models as corpus_models  # noqa: F401
from app.db.base import Base, transaction
from app.llm import models as llm_models  # noqa: F401
from app.registry.seed import BANKS, seed_banks
from app.tariffs import models as tariff_models  # noqa: F401


def test_initial_registry_schema_contains_only_catalog_and_ingestion_tables() -> None:
    assert set(Base.metadata.tables) == {
        "banks",
        "source_policies",
        "sources",
        "blobs",
        "source_versions",
        "source_fetches",
        "snapshots",
        "extraction_runs",
        "document_chunks",
        "snapshot_members",
        "tariff_candidates",
        "evidence_refs",
        "fact_reviews",
        "published_facts",
        "llm_usage",
        "users",
        "invitations",
        "password_resets",
        "sessions",
        "auth_audit",
    }


def test_seed_contains_four_bank_codes_without_tariff_or_source_rows() -> None:
    assert [code for code, _ in BANKS] == ["sber", "vtb", "alfa", "kuban_credit"]


def test_initial_schema_constraints_and_foreign_keys_are_declared() -> None:
    tables = Base.metadata.tables
    assert "uq_sources_bank_canonical_url" in {item.name for item in tables["sources"].constraints}
    assert "ck_blobs_size_positive" in {item.name for item in tables["blobs"].constraints}
    assert any(
        fk.target_fullname == "source_versions.id" for fk in tables["source_fetches"].foreign_keys
    )
    assert "job_run_id" not in tables["source_fetches"].columns
    assert "schedule_seconds" not in tables["sources"].columns
    assert "next_check_at" not in tables["sources"].columns


def test_bank_seed_uses_postgres_conflict_safe_insert_and_no_sources() -> None:
    class StatementCapture:
        statement = None

        def execute(self, statement):
            self.statement = statement

    capture = StatementCapture()
    seed_banks(capture)  # type: ignore[arg-type]
    sql = str(capture.statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (code) DO NOTHING" in sql
    assert "sources" not in sql


def test_transaction_commits_on_success_and_rolls_back_on_error() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    table = Table("values_table", MetaData(), Column("value", Integer, primary_key=True))
    table.create(engine)
    factory = sessionmaker(engine)

    with transaction(factory) as session:
        session.execute(table.insert().values(value=1))
    with pytest.raises(RuntimeError):
        with transaction(factory) as session:
            session.execute(table.insert().values(value=2))
            raise RuntimeError("rollback")

    with factory() as session:
        assert list(session.scalars(select(table.c.value))) == [1]
    engine.dispose()
