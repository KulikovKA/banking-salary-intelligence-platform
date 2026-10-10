"""Allow reviewed draft publication before final corpus freeze.

Sequential integration correction to SNAP-02; original migrations remain intact.
"""
# ruff: noqa: E501
from alembic import op

revision = "0004a_corpus_gates"
down_revision = "0004_snapshot_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
CREATE OR REPLACE FUNCTION bsi_published_fact_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE snapshot_state text; snapshot_corpus text; candidate_corpus text;
                candidate_extraction uuid; review_candidate uuid; review_decision text; review_valid boolean;
        BEGIN
            SELECT state, corpus_kind INTO snapshot_state, snapshot_corpus FROM snapshots WHERE id = NEW.snapshot_id FOR UPDATE;
            SELECT corpus_kind, extraction_run_id INTO candidate_corpus, candidate_extraction
                FROM tariff_candidates WHERE id = NEW.candidate_id;
            SELECT candidate_id, decision, (validation->>'valid')::boolean
                INTO review_candidate, review_decision, review_valid FROM fact_reviews WHERE id = NEW.review_id;
            IF snapshot_state IS DISTINCT FROM 'draft' OR snapshot_corpus IS DISTINCT FROM candidate_corpus
                OR review_candidate IS DISTINCT FROM NEW.candidate_id OR review_decision IS DISTINCT FROM 'approved'
                OR review_valid IS DISTINCT FROM true OR NOT EXISTS (
                    SELECT 1 FROM snapshot_members m WHERE m.snapshot_id = NEW.snapshot_id
                    AND m.extraction_run_id = candidate_extraction
                ) THEN
                RAISE EXCEPTION 'publication requires matching draft member and valid approved review'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE FUNCTION bsi_snapshot_ready_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.state = 'draft' AND NEW.state = 'frozen' AND (
                EXISTS (
                    SELECT 1 FROM snapshot_members m WHERE m.snapshot_id = NEW.id
                    AND NOT EXISTS (
                        SELECT 1 FROM published_facts f
                        JOIN tariff_candidates c ON c.id = f.candidate_id
                        WHERE f.snapshot_id = NEW.id AND c.extraction_run_id = m.extraction_run_id
                    )
                ) OR EXISTS (
                    SELECT 1 FROM published_facts f JOIN tariff_candidates c ON c.id = f.candidate_id
                    WHERE f.snapshot_id = NEW.id AND NOT EXISTS (
                        SELECT 1 FROM snapshot_members m WHERE m.snapshot_id = NEW.id
                        AND m.extraction_run_id = c.extraction_run_id
                    )
                )
            ) THEN
                RAISE EXCEPTION 'freeze requires reviewed publication for every exact member'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_snapshots_ready BEFORE UPDATE ON snapshots
            FOR EACH ROW EXECUTE FUNCTION bsi_snapshot_ready_guard();

    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_snapshots_ready ON snapshots")
    op.execute("DROP FUNCTION bsi_snapshot_ready_guard()")
    op.execute(r"""
CREATE OR REPLACE FUNCTION bsi_published_fact_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
    """)
