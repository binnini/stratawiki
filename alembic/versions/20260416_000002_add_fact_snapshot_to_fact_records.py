"""add fact snapshot membership to fact records

Revision ID: 20260416_000002
Revises: 20260415_000001
Create Date: 2026-04-16 00:00:02
"""
from __future__ import annotations

from alembic import op


revision = "20260416_000002"
down_revision = "20260415_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE fact.record_envelopes
        ADD COLUMN IF NOT EXISTS fact_snapshot_id text NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_fact_record_envelopes_fact_snapshot
        ON fact.record_envelopes (fact_snapshot_id)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_fact_record_envelopes_fact_snapshot
        """
    )
    op.execute(
        """
        ALTER TABLE fact.record_envelopes
        DROP COLUMN IF EXISTS fact_snapshot_id
        """
    )
