"""initial Postgres logical schemas for stratawiki v1

Revision ID: 20260415_000001
Revises: 
Create Date: 2026-04-15 00:00:01
"""
from __future__ import annotations

from alembic import op


revision = "20260415_000001"
down_revision = None
branch_labels = None
depends_on = None


SCOPE_CHECK = "scope IN ('shared', 'tenant', 'user')"
SCOPE_SHAPE_CHECK = "((scope = 'shared' AND tenant_id IS NULL AND user_id IS NULL) OR (scope = 'tenant' AND tenant_id IS NOT NULL AND user_id IS NULL) OR (scope = 'user' AND tenant_id IS NOT NULL AND user_id IS NOT NULL))"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    for schema_name in ("fact", "interp", "personal", "ops", "graph"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

    op.execute(
        f"""
        CREATE TABLE fact.record_envelopes (
            id text PRIMARY KEY,
            domain text NOT NULL,
            entity_type text NOT NULL,
            canonical_key text NOT NULL,
            scope text NOT NULL CHECK ({SCOPE_CHECK}),
            tenant_id text NULL,
            user_id text NULL,
            schema_version text NOT NULL,
            attributes_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            provenance_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_fact_record_scope_shape CHECK ({SCOPE_SHAPE_CHECK})
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_fact_record_envelopes_canonical_scope
        ON fact.record_envelopes (
            domain,
            canonical_key,
            scope,
            COALESCE(tenant_id, ''),
            COALESCE(user_id, '')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fact_record_envelopes_domain_entity_scope
        ON fact.record_envelopes (domain, entity_type, scope, tenant_id, user_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE fact.relation_envelopes (
            id bigserial PRIMARY KEY,
            domain text NOT NULL,
            relation_type text NOT NULL,
            from_canonical_key text NOT NULL,
            to_canonical_key text NOT NULL,
            scope text NOT NULL CHECK ({SCOPE_CHECK}),
            tenant_id text NULL,
            user_id text NULL,
            schema_version text NOT NULL,
            attributes_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            provenance_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_fact_relation_scope_shape CHECK ({SCOPE_SHAPE_CHECK})
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_fact_relation_envelopes_natural_key
        ON fact.relation_envelopes (
            domain,
            relation_type,
            from_canonical_key,
            to_canonical_key,
            scope,
            COALESCE(tenant_id, ''),
            COALESCE(user_id, '')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_fact_relation_envelopes_from_lookup
        ON fact.relation_envelopes (
            domain,
            from_canonical_key,
            relation_type,
            scope,
            tenant_id,
            user_id
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE interp.record (
            id text PRIMARY KEY,
            domain text NOT NULL,
            kind text NOT NULL,
            subject_type text NOT NULL,
            subject_id text NOT NULL,
            scope text NOT NULL CHECK ({SCOPE_CHECK}),
            tenant_id text NULL,
            user_id text NULL,
            schema_version text NOT NULL,
            status text NOT NULL,
            confidence double precision NOT NULL,
            computed_at timestamptz NOT NULL,
            expires_at timestamptz NULL,
            body_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            provenance_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            render_hints_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            fact_snapshot_id text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_interp_record_scope_shape CHECK ({SCOPE_SHAPE_CHECK})
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_interp_record_subject_scope
        ON interp.record (domain, subject_type, subject_id, scope, tenant_id, user_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_interp_record_fact_snapshot
        ON interp.record (fact_snapshot_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE personal.record (
            id text PRIMARY KEY,
            domain text NOT NULL,
            kind text NOT NULL,
            title text NOT NULL,
            summary text NOT NULL,
            scope text NOT NULL CHECK ({SCOPE_CHECK}),
            tenant_id text NULL,
            user_id text NULL,
            fact_snapshot_id text NOT NULL,
            interpretation_snapshot_id text NULL,
            profile_version text NULL,
            body_path text NOT NULL,
            status text NOT NULL,
            schema_version text NOT NULL,
            provenance_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_personal_record_scope_shape CHECK ({SCOPE_SHAPE_CHECK})
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_personal_record_scope_lookup
        ON personal.record (domain, kind, scope, tenant_id, user_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_personal_record_snapshot_lookup
        ON personal.record (fact_snapshot_id, interpretation_snapshot_id, profile_version)
        """
    )

    op.execute(
        """
        CREATE TABLE personal.profile_context (
            id bigserial PRIMARY KEY,
            domain text NOT NULL,
            tenant_id text NOT NULL,
            user_id text NOT NULL,
            profile_version text NOT NULL,
            goals_json jsonb NOT NULL DEFAULT '[]'::jsonb,
            preferences_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            attributes_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_personal_profile_context_domain_scope
        ON personal.profile_context (domain, tenant_id, user_id)
        """
    )

    op.execute(
        """
        CREATE TABLE ops.snapshot_pointer (
            layer text NOT NULL,
            domain text NOT NULL,
            current_snapshot_id text NOT NULL,
            fact_snapshot_id text NOT NULL,
            interpretation_snapshot_id text NULL,
            profile_version text NULL,
            updated_at timestamptz NOT NULL DEFAULT NOW(),
            PRIMARY KEY (layer, domain)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ops.snapshot_publication (
            snapshot_id text NOT NULL,
            layer text NOT NULL,
            domain text NOT NULL,
            fact_snapshot_id text NOT NULL,
            interpretation_snapshot_id text NULL,
            profile_version text NULL,
            metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            published_at timestamptz NOT NULL DEFAULT NOW(),
            PRIMARY KEY (snapshot_id, layer, domain)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_ops_snapshot_publication_layer_domain_published
        ON ops.snapshot_publication (layer, domain, published_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE ops.outbox_event (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            idempotency_key text NULL UNIQUE,
            event_type text NOT NULL,
            aggregate_layer text NOT NULL,
            aggregate_id text NOT NULL,
            payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            status text NOT NULL CHECK (status IN ('pending', 'claimed', 'processed', 'failed')),
            attempt_count integer NOT NULL DEFAULT 0,
            available_at timestamptz NOT NULL DEFAULT NOW(),
            claimed_at timestamptz NULL,
            processed_at timestamptz NULL,
            last_error text NULL,
            created_at timestamptz NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_ops_outbox_event_status_available
        ON ops.outbox_event (status, available_at, created_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_ops_outbox_event_aggregate_lookup
        ON ops.outbox_event (aggregate_layer, aggregate_id, created_at)
        """
    )

    op.execute(
        f"""
        CREATE TABLE graph.dependency_edge (
            id bigserial PRIMARY KEY,
            domain text NOT NULL,
            from_layer text NOT NULL,
            from_id text NOT NULL,
            to_layer text NOT NULL,
            to_id text NOT NULL,
            scope text NOT NULL CHECK ({SCOPE_CHECK}),
            tenant_id text NULL,
            user_id text NULL,
            edge_type text NULL,
            attributes_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_graph_dependency_edge_scope_shape CHECK ({SCOPE_SHAPE_CHECK})
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_graph_dependency_edge_reverse_lookup
        ON graph.dependency_edge (domain, from_layer, from_id, scope, tenant_id, user_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_graph_dependency_edge_to_lookup
        ON graph.dependency_edge (domain, to_layer, to_id, scope, tenant_id, user_id)
        """
    )

    op.execute(
        f"""
        CREATE TABLE graph.rendered_page (
            id bigserial PRIMARY KEY,
            domain text NOT NULL,
            layer text NOT NULL,
            record_id text NOT NULL,
            path text NOT NULL,
            scope text NOT NULL CHECK ({SCOPE_CHECK}),
            tenant_id text NULL,
            user_id text NULL,
            fact_snapshot_id text NOT NULL,
            interpretation_snapshot_id text NULL,
            profile_version text NULL,
            metadata_json jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_graph_rendered_page_scope_shape CHECK ({SCOPE_SHAPE_CHECK})
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_graph_rendered_page_record_scope
        ON graph.rendered_page (
            domain,
            layer,
            record_id,
            scope,
            COALESCE(tenant_id, ''),
            COALESCE(user_id, '')
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_graph_rendered_page_path
        ON graph.rendered_page (path)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_graph_rendered_page_lookup
        ON graph.rendered_page (layer, record_id, scope, tenant_id, user_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph.rendered_page")
    op.execute("DROP TABLE IF EXISTS graph.dependency_edge")
    op.execute("DROP TABLE IF EXISTS ops.outbox_event")
    op.execute("DROP TABLE IF EXISTS ops.snapshot_publication")
    op.execute("DROP TABLE IF EXISTS ops.snapshot_pointer")
    op.execute("DROP TABLE IF EXISTS personal.profile_context")
    op.execute("DROP TABLE IF EXISTS personal.record")
    op.execute("DROP TABLE IF EXISTS interp.record")
    op.execute("DROP TABLE IF EXISTS fact.relation_envelopes")
    op.execute("DROP TABLE IF EXISTS fact.record_envelopes")

    for schema_name in ("graph", "ops", "personal", "interp", "fact"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema_name}")
