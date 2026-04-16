"""add retrieval FTS indexes

Revision ID: 20260416_000003
Revises: 20260416_000002
Create Date: 2026-04-16 00:00:03
"""
from __future__ import annotations

from alembic import op


revision = "20260416_000003"
down_revision = "20260416_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_fact_record_envelopes_retrieval_fts
        ON fact.record_envelopes
        USING GIN (
            to_tsvector(
                'simple',
                regexp_replace(
                    lower(
                        concat_ws(
                            ' ',
                            COALESCE(id, ''),
                            COALESCE(entity_type, ''),
                            COALESCE(canonical_key, ''),
                            COALESCE(attributes_json->>'title', ''),
                            COALESCE(attributes_json->>'name', ''),
                            COALESCE(attributes_json->>'label', ''),
                            COALESCE(attributes_json->>'summary', ''),
                            COALESCE(attributes_json->>'description', ''),
                            COALESCE(attributes_json->>'headline', '')
                        )
                    ),
                    '[^a-z0-9]+',
                    ' ',
                    'g'
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_interp_record_retrieval_fts
        ON interp.record
        USING GIN (
            to_tsvector(
                'simple',
                regexp_replace(
                    lower(
                        concat_ws(
                            ' ',
                            COALESCE(id, ''),
                            COALESCE(kind, ''),
                            COALESCE(subject_type, ''),
                            COALESCE(subject_id, ''),
                            COALESCE(body_json->>'summary', ''),
                            COALESCE(body_json->>'thesis', ''),
                            COALESCE(body_json->>'headline', ''),
                            COALESCE(body_json->>'title', '')
                        )
                    ),
                    '[^a-z0-9]+',
                    ' ',
                    'g'
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_personal_record_retrieval_fts
        ON personal.record
        USING GIN (
            to_tsvector(
                'simple',
                regexp_replace(
                    lower(
                        concat_ws(
                            ' ',
                            COALESCE(id, ''),
                            COALESCE(kind, ''),
                            COALESCE(title, ''),
                            COALESCE(summary, ''),
                            COALESCE(body_path, '')
                        )
                    ),
                    '[^a-z0-9]+',
                    ' ',
                    'g'
                )
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS personal.ix_personal_record_retrieval_fts")
    op.execute("DROP INDEX IF EXISTS interp.ix_interp_record_retrieval_fts")
    op.execute("DROP INDEX IF EXISTS fact.ix_fact_record_envelopes_retrieval_fts")
