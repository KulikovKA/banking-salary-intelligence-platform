"""Add immutable extraction, snapshots, tariff review, and usage accounting.

Revision ID: 0004_snapshot_core
Revises: 0003_operator_only
"""

# Stored PostgreSQL trigger bodies are intentionally kept as readable SQL blocks.
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_snapshot_core"
down_revision: str | None = "0003_operator_only"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("corpus_kind", sa.String(20), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("frozen_at", sa.DateTime(timezone=True)),
        sa.Column("manifest_sha256", sa.String(64)),
        sa.CheckConstraint("revision > 0", name="ck_snapshots_revision_positive"),
        sa.CheckConstraint("corpus_kind in ('real', 'synthetic')", name="ck_snapshots_corpus"),
        sa.CheckConstraint("state in ('draft', 'frozen', 'revoked')", name="ck_snapshots_state"),
        sa.CheckConstraint(
            "(state = 'draft' and frozen_at is null and manifest_sha256 is null) or "
            "(state in ('frozen', 'revoked') and frozen_at is not null "
            "and manifest_sha256 ~ '^[0-9a-f]{64}$')",
            name="ck_snapshots_freeze_fields",
        ),
        sa.UniqueConstraint("revision", name="uq_snapshots_revision"),
    )
    op.create_table(
        "extraction_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("raw_sha256", sa.String(64), nullable=False),
        sa.Column("extraction_sha256", sa.String(64), nullable=False),
        sa.Column("parser_version", sa.String(200), nullable=False),
        sa.Column("corpus_kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("raw_sha256 ~ '^[0-9a-f]{64}$'", name="ck_extraction_runs_raw_sha256"),
        sa.CheckConstraint(
            "extraction_sha256 ~ '^[0-9a-f]{64}$'", name="ck_extraction_runs_extraction_sha256"
        ),
        sa.CheckConstraint(
            "corpus_kind in ('real', 'synthetic')", name="ck_extraction_runs_corpus"
        ),
        sa.CheckConstraint(
            "status in ('ok', 'needs_ocr', 'unsupported', 'failed')",
            name="ck_extraction_runs_status",
        ),
        sa.UniqueConstraint(
            "source_version_id",
            "parser_version",
            "extraction_sha256",
            name="uq_extraction_runs_version_parser_hash",
        ),
    )
    op.create_index(
        "ix_extraction_runs_source_version_id", "extraction_runs", ["source_version_id"]
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("locator", postgresql.JSONB(), nullable=False),
        sa.Column("relations", postgresql.JSONB(), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=False),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("ordinal >= 0", name="ck_document_chunks_ordinal_nonnegative"),
        sa.CheckConstraint("text_sha256 ~ '^[0-9a-f]{64}$'", name="ck_document_chunks_text_sha256"),
        sa.UniqueConstraint("extraction_run_id", "ordinal", name="uq_document_chunks_run_ordinal"),
    )
    op.create_index(
        "ix_document_chunks_extraction_ordinal", "document_chunks", ["extraction_run_id", "ordinal"]
    )
    op.create_index(
        "ix_document_chunks_search_vector",
        "document_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_table(
        "snapshot_members",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "source_version_id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False
        ),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "snapshot_id", "extraction_run_id", name="uq_snapshot_members_extraction"
        ),
    )
    op.create_index(
        "ix_snapshot_members_source_version_id", "snapshot_members", ["source_version_id"]
    )
    op.create_table(
        "tariff_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("bank_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("metric_code", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("corpus_kind", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bank_id"], ["banks.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "corpus_kind in ('real', 'synthetic')", name="ck_tariff_candidates_corpus"
        ),
        sa.CheckConstraint(
            "metric_code ~ '^[a-z][a-z0-9_]{1,63}$'", name="ck_tariff_candidates_metric"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_tariff_candidates_payload_object"
        ),
        sa.CheckConstraint(
            "payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_tariff_candidates_payload_sha256"
        ),
    )
    op.create_index(
        "ix_tariff_candidates_bank_metric", "tariff_candidates", ["bank_id", "metric_code"]
    )
    op.create_index(
        "ix_tariff_candidates_extraction_run_id", "tariff_candidates", ["extraction_run_id"]
    )
    op.create_index("ix_tariff_candidates_corpus_kind", "tariff_candidates", ["corpus_kind"])
    op.create_table(
        "evidence_refs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("raw_sha256", sa.String(64), nullable=False),
        sa.Column("extraction_sha256", sa.String(64), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("quote_start", sa.Integer(), nullable=False),
        sa.Column("quote_end", sa.Integer(), nullable=False),
        sa.Column("locator", postgresql.JSONB(), nullable=False),
        sa.Column("support_role", sa.String(20), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["tariff_candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("raw_sha256 ~ '^[0-9a-f]{64}$'", name="ck_evidence_refs_raw_sha256"),
        sa.CheckConstraint(
            "extraction_sha256 ~ '^[0-9a-f]{64}$'", name="ck_evidence_refs_extraction_sha256"
        ),
        sa.CheckConstraint("quote_start >= 0", name="ck_evidence_refs_quote_start"),
        sa.CheckConstraint("quote_end > quote_start", name="ck_evidence_refs_quote_end"),
        sa.CheckConstraint(
            "quote_end - quote_start = char_length(quote)", name="ck_evidence_refs_quote_length"
        ),
        sa.CheckConstraint(
            "support_role in ('value', 'unit', 'basis', 'condition', 'scope', 'date')",
            name="ck_evidence_refs_support_role",
        ),
    )
    op.create_index("ix_evidence_refs_candidate_id", "evidence_refs", ["candidate_id"])
    op.create_index("ix_evidence_refs_chunk_id", "evidence_refs", ["chunk_id"])
    op.create_table(
        "fact_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("reviewer_label", sa.String(200), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False)),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("validation", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["tariff_candidates.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "decision in ('approved', 'rejected', 'needs_review')", name="ck_fact_reviews_decision"
        ),
        sa.CheckConstraint(
            "reviewer_label = 'operator' or length(btrim(reviewer_label)) > 0",
            name="ck_fact_reviews_reviewer_label",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(validation) = 'object'", name="ck_fact_reviews_validation"
        ),
    )
    op.create_index(
        "ix_fact_reviews_candidate_created", "fact_reviews", ["candidate_id", "created_at"]
    )
    op.create_table(
        "published_facts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_id"], ["tariff_candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["review_id"], ["fact_reviews.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "snapshot_id", "candidate_id", name="uq_published_facts_snapshot_candidate"
        ),
        sa.UniqueConstraint("review_id", name="uq_published_facts_review"),
    )
    op.create_index("ix_published_facts_snapshot_id", "published_facts", ["snapshot_id"])
    op.create_table(
        "llm_usage",
        sa.Column("request_id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False)),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("actual_tokens", sa.Integer()),
        sa.Column("estimated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("state", sa.String(20), nullable=False, server_default="reserved"),
        sa.Column("model_id", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("window_started_at <= created_at", name="ck_llm_usage_window_start"),
        sa.CheckConstraint("reserved_tokens > 0", name="ck_llm_usage_reserved_positive"),
        sa.CheckConstraint(
            "prompt_tokens is null or prompt_tokens >= 0", name="ck_llm_usage_prompt_tokens"
        ),
        sa.CheckConstraint(
            "completion_tokens is null or completion_tokens >= 0",
            name="ck_llm_usage_completion_tokens",
        ),
        sa.CheckConstraint(
            "actual_tokens is null or actual_tokens >= 0",
            name="ck_llm_usage_actual_tokens",
        ),
        sa.CheckConstraint(
            "state in ('reserved', 'settled', 'released', 'failed')", name="ck_llm_usage_state"
        ),
        sa.CheckConstraint(
            "(state = 'settled' and prompt_tokens is not null and completion_tokens is not null "
            "and actual_tokens = prompt_tokens + completion_tokens) or "
            "(state != 'settled' and actual_tokens is null)",
            name="ck_llm_usage_settled_tokens",
        ),
    )
    op.create_index("ix_llm_usage_user_window", "llm_usage", ["user_id", "window_started_at"])
    op.create_index("ix_llm_usage_state_created", "llm_usage", ["state", "created_at"])

    op.execute(
        """
        CREATE FUNCTION bsi_reject_immutable_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'immutable record in % cannot be changed', TG_TABLE_NAME
                USING ERRCODE = '55000';
        END;
        $$;
        CREATE FUNCTION bsi_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE member_count bigint;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.state <> 'draft' OR NEW.frozen_at IS NOT NULL OR NEW.manifest_sha256 IS NOT NULL THEN
                    RAISE EXCEPTION 'snapshot must begin as draft' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' THEN
                IF OLD.state <> 'draft' THEN
                    RAISE EXCEPTION 'frozen snapshot cannot be deleted' USING ERRCODE = '55000';
                END IF;
                RETURN OLD;
            END IF;
            IF NEW.id <> OLD.id OR NEW.revision <> OLD.revision OR NEW.corpus_kind <> OLD.corpus_kind
                OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'snapshot identity is immutable' USING ERRCODE = '55000';
            END IF;
            IF OLD.state = 'draft' AND NEW.state = 'frozen' THEN
                IF NEW.frozen_at IS NULL OR NEW.manifest_sha256 IS NULL THEN
                    RAISE EXCEPTION 'freezing requires timestamp and manifest hash' USING ERRCODE = '23514';
                END IF;
                SELECT count(*) INTO member_count FROM snapshot_members WHERE snapshot_id = OLD.id;
                IF member_count = 0 THEN
                    RAISE EXCEPTION 'cannot freeze an empty snapshot' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            ELSIF OLD.state = 'frozen' AND NEW.state = 'revoked' THEN
                IF NEW.frozen_at <> OLD.frozen_at OR NEW.manifest_sha256 <> OLD.manifest_sha256 THEN
                    RAISE EXCEPTION 'revocation cannot alter frozen snapshot metadata' USING ERRCODE = '55000';
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'invalid snapshot state transition' USING ERRCODE = '55000';
        END;
        $$;
        CREATE FUNCTION bsi_snapshot_member_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE target_snapshot uuid; snapshot_state text; snapshot_corpus text;
                version_corpus text; version_state text; blob_hash text; blob_corpus text;
                source_corpus text; extraction_source uuid; extraction_hash text;
                extraction_corpus text; extraction_status text;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                target_snapshot := OLD.snapshot_id;
            ELSE
                target_snapshot := NEW.snapshot_id;
            END IF;
            SELECT state, corpus_kind INTO snapshot_state, snapshot_corpus
                FROM snapshots WHERE id = target_snapshot FOR UPDATE;
            IF snapshot_state IS DISTINCT FROM 'draft' THEN
                RAISE EXCEPTION 'snapshot membership is immutable after freeze' USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            IF TG_OP = 'UPDATE' THEN
                SELECT state INTO snapshot_state
                    FROM snapshots WHERE id = OLD.snapshot_id FOR UPDATE;
                IF snapshot_state IS DISTINCT FROM 'draft' THEN
                    RAISE EXCEPTION 'snapshot membership is immutable after freeze' USING ERRCODE = '55000';
                END IF;
            END IF;
            SELECT v.content_state, b.sha256, b.corpus_kind, s.corpus_kind
                INTO version_state, blob_hash, blob_corpus, source_corpus
                FROM source_versions v JOIN blobs b ON b.id = v.blob_id
                JOIN sources s ON s.id = v.source_id WHERE v.id = NEW.source_version_id;
            SELECT source_version_id, raw_sha256, corpus_kind, status
                INTO extraction_source, extraction_hash, extraction_corpus, extraction_status
                FROM extraction_runs WHERE id = NEW.extraction_run_id;
            IF version_state IS DISTINCT FROM 'accepted' OR extraction_source IS DISTINCT FROM NEW.source_version_id
                OR extraction_status IS DISTINCT FROM 'ok' OR extraction_hash IS DISTINCT FROM blob_hash
                OR snapshot_corpus IS DISTINCT FROM extraction_corpus OR source_corpus IS DISTINCT FROM blob_corpus
                OR blob_corpus IS DISTINCT FROM extraction_corpus THEN
                RAISE EXCEPTION 'snapshot member provenance or corpus mismatch' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE FUNCTION bsi_extraction_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE version_state text; source_corpus text; blob_corpus text; blob_hash text;
        BEGIN
            SELECT v.content_state, s.corpus_kind, b.corpus_kind, b.sha256
                INTO version_state, source_corpus, blob_corpus, blob_hash
                FROM source_versions v JOIN sources s ON s.id = v.source_id
                JOIN blobs b ON b.id = v.blob_id WHERE v.id = NEW.source_version_id;
            IF version_state IS DISTINCT FROM 'accepted' OR NEW.raw_sha256 IS DISTINCT FROM blob_hash
                OR NEW.corpus_kind IS DISTINCT FROM source_corpus OR source_corpus IS DISTINCT FROM blob_corpus THEN
                RAISE EXCEPTION 'extraction provenance mismatch or source version not accepted' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE FUNCTION bsi_chunk_search_vector() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.search_vector := to_tsvector('russian', NEW.text) || to_tsvector('simple', NEW.text);
            RETURN NEW;
        END;
        $$;
        CREATE FUNCTION bsi_chunk_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE extraction_status text;
        BEGIN
            SELECT status INTO extraction_status FROM extraction_runs WHERE id = NEW.extraction_run_id;
            IF extraction_status IS DISTINCT FROM 'ok' THEN
                RAISE EXCEPTION 'chunks require a successful extraction' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE FUNCTION bsi_candidate_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE extraction_corpus text; extraction_status text; bank_code text;
        BEGIN
            SELECT corpus_kind, status INTO extraction_corpus, extraction_status
                FROM extraction_runs WHERE id = NEW.extraction_run_id;
            SELECT code INTO bank_code FROM banks WHERE id = NEW.bank_id;
            IF extraction_status IS DISTINCT FROM 'ok' OR NEW.corpus_kind IS DISTINCT FROM extraction_corpus
                OR NEW.payload->>'id' IS DISTINCT FROM NEW.id::text
                OR NEW.payload->>'bank_code' IS DISTINCT FROM bank_code
                OR NEW.payload->>'metric_code' IS DISTINCT FROM NEW.metric_code
                OR NEW.payload->>'corpus_kind' IS DISTINCT FROM NEW.corpus_kind
                OR NEW.payload->>'publication_state' IS DISTINCT FROM 'pending_review' THEN
                RAISE EXCEPTION 'candidate payload or provenance mismatch' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE FUNCTION bsi_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE candidate_extraction uuid; candidate_corpus text; chunk_extraction uuid;
                chunk_text text; chunk_locator jsonb; extraction_source uuid;
                extraction_hash text; extraction_raw text; blob_hash text; source_corpus text;
        BEGIN
            SELECT extraction_run_id, corpus_kind INTO candidate_extraction, candidate_corpus
                FROM tariff_candidates WHERE id = NEW.candidate_id;
            SELECT extraction_run_id, text, locator INTO chunk_extraction, chunk_text, chunk_locator
                FROM document_chunks WHERE id = NEW.chunk_id;
            SELECT e.source_version_id, e.extraction_sha256, e.raw_sha256, b.sha256, s.corpus_kind
                INTO extraction_source, extraction_hash, extraction_raw, blob_hash, source_corpus
                FROM extraction_runs e JOIN source_versions v ON v.id = e.source_version_id
                JOIN blobs b ON b.id = v.blob_id JOIN sources s ON s.id = v.source_id
                WHERE e.id = NEW.extraction_run_id;
            IF candidate_extraction IS DISTINCT FROM NEW.extraction_run_id
                OR chunk_extraction IS DISTINCT FROM NEW.extraction_run_id
                OR extraction_source IS DISTINCT FROM NEW.source_version_id
                OR extraction_hash IS DISTINCT FROM NEW.extraction_sha256
                OR extraction_raw IS DISTINCT FROM NEW.raw_sha256 OR blob_hash IS DISTINCT FROM NEW.raw_sha256
                OR candidate_corpus IS DISTINCT FROM source_corpus
                OR substring(chunk_text from NEW.quote_start + 1 for NEW.quote_end - NEW.quote_start)
                    IS DISTINCT FROM NEW.quote
                OR chunk_locator IS DISTINCT FROM NEW.locator THEN
                RAISE EXCEPTION 'evidence provenance, quote, or locator mismatch' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE FUNCTION bsi_published_fact_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE snapshot_state text; snapshot_corpus text; candidate_corpus text;
                candidate_extraction uuid; review_candidate uuid; review_decision text; review_valid boolean;
        BEGIN
            SELECT state, corpus_kind INTO snapshot_state, snapshot_corpus FROM snapshots WHERE id = NEW.snapshot_id;
            SELECT corpus_kind, extraction_run_id INTO candidate_corpus, candidate_extraction
                FROM tariff_candidates WHERE id = NEW.candidate_id;
            SELECT candidate_id, decision, (validation->>'valid')::boolean
                INTO review_candidate, review_decision, review_valid FROM fact_reviews WHERE id = NEW.review_id;
            IF snapshot_state IS DISTINCT FROM 'frozen' OR snapshot_corpus IS DISTINCT FROM candidate_corpus
                OR review_candidate IS DISTINCT FROM NEW.candidate_id OR review_decision IS DISTINCT FROM 'approved'
                OR review_valid IS DISTINCT FROM true OR NOT EXISTS (
                    SELECT 1 FROM snapshot_members m WHERE m.snapshot_id = NEW.snapshot_id
                    AND m.extraction_run_id = candidate_extraction
                ) THEN
                RAISE EXCEPTION 'publication requires matching frozen member and valid approved review'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_snapshots_guard BEFORE INSERT OR UPDATE OR DELETE ON snapshots
            FOR EACH ROW EXECUTE FUNCTION bsi_snapshot_guard();
        CREATE TRIGGER trg_snapshot_members_guard BEFORE INSERT OR UPDATE OR DELETE ON snapshot_members
            FOR EACH ROW EXECUTE FUNCTION bsi_snapshot_member_guard();
        CREATE TRIGGER trg_extraction_runs_guard BEFORE INSERT ON extraction_runs
            FOR EACH ROW EXECUTE FUNCTION bsi_extraction_guard();
        CREATE TRIGGER trg_document_chunks_search BEFORE INSERT ON document_chunks
            FOR EACH ROW EXECUTE FUNCTION bsi_chunk_search_vector();
        CREATE TRIGGER trg_document_chunks_guard BEFORE INSERT ON document_chunks
            FOR EACH ROW EXECUTE FUNCTION bsi_chunk_guard();
        CREATE TRIGGER trg_tariff_candidates_guard BEFORE INSERT ON tariff_candidates
            FOR EACH ROW EXECUTE FUNCTION bsi_candidate_guard();
        CREATE TRIGGER trg_evidence_refs_guard BEFORE INSERT ON evidence_refs
            FOR EACH ROW EXECUTE FUNCTION bsi_evidence_guard();
        CREATE TRIGGER trg_published_facts_guard BEFORE INSERT ON published_facts
            FOR EACH ROW EXECUTE FUNCTION bsi_published_fact_guard();
        CREATE TRIGGER trg_extraction_runs_immutable BEFORE UPDATE OR DELETE ON extraction_runs
            FOR EACH ROW EXECUTE FUNCTION bsi_reject_immutable_mutation();
        CREATE TRIGGER trg_document_chunks_immutable BEFORE UPDATE OR DELETE ON document_chunks
            FOR EACH ROW EXECUTE FUNCTION bsi_reject_immutable_mutation();
        CREATE TRIGGER trg_tariff_candidates_immutable BEFORE UPDATE OR DELETE ON tariff_candidates
            FOR EACH ROW EXECUTE FUNCTION bsi_reject_immutable_mutation();
        CREATE TRIGGER trg_evidence_refs_immutable BEFORE UPDATE OR DELETE ON evidence_refs
            FOR EACH ROW EXECUTE FUNCTION bsi_reject_immutable_mutation();
        CREATE TRIGGER trg_fact_reviews_append_only BEFORE UPDATE OR DELETE ON fact_reviews
            FOR EACH ROW EXECUTE FUNCTION bsi_reject_immutable_mutation();
        CREATE TRIGGER trg_published_facts_immutable BEFORE UPDATE OR DELETE ON published_facts
            FOR EACH ROW EXECUTE FUNCTION bsi_reject_immutable_mutation();
        """
    )


def downgrade() -> None:
    raise RuntimeError("SNAPSHOT_EVIDENCE_DOWNGRADE_REQUIRES_REVIEW")
