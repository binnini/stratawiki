CREATE SCHEMA IF NOT EXISTS fact;
CREATE SCHEMA IF NOT EXISTS interp;
CREATE SCHEMA IF NOT EXISTS personal;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS graph;

CREATE TABLE IF NOT EXISTS fact.record_envelopes (
    id TEXT PRIMARY KEY,
    layer TEXT NOT NULL,
    domain TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('shared', 'tenant', 'user')),
    fact_snapshot_id TEXT NOT NULL,
    tenant_id TEXT,
    user_id TEXT,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_version TEXT NOT NULL,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS fact_record_envelopes_canonical_scope_key
    ON fact.record_envelopes (
        domain,
        canonical_key,
        scope,
        COALESCE(tenant_id, ''),
        COALESCE(user_id, '')
    );

CREATE INDEX IF NOT EXISTS fact_record_envelopes_scope_updated_idx
    ON fact.record_envelopes (domain, scope, tenant_id, user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS fact.relation_envelopes (
    id BIGSERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    from_canonical_key TEXT NOT NULL,
    to_canonical_key TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('shared', 'tenant', 'user')),
    tenant_id TEXT,
    user_id TEXT,
    schema_version TEXT NOT NULL,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS fact_relation_envelopes_identity_key
    ON fact.relation_envelopes (
        domain,
        relation_type,
        from_canonical_key,
        to_canonical_key,
        scope,
        COALESCE(tenant_id, ''),
        COALESCE(user_id, '')
    );

CREATE INDEX IF NOT EXISTS fact_relation_envelopes_target_idx
    ON fact.relation_envelopes (
        domain,
        to_canonical_key,
        scope,
        tenant_id,
        user_id
    );

CREATE TABLE IF NOT EXISTS interp.record (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    family TEXT NOT NULL,
    kind TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('shared', 'tenant', 'user')),
    tenant_id TEXT,
    user_id TEXT,
    schema_version TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    title TEXT,
    claim TEXT,
    summary TEXT,
    body_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    render_hints_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    fact_snapshot_id TEXT NOT NULL,
    interpretation_snapshot_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS interp_record_partition_idx
    ON interp.record (
        domain,
        family,
        kind,
        subject_type,
        subject_id,
        scope,
        tenant_id,
        user_id,
        updated_at DESC
    );

CREATE TABLE IF NOT EXISTS personal.record (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope = 'user'),
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    fact_snapshot_id TEXT NOT NULL,
    interpretation_snapshot_id TEXT,
    profile_version TEXT NOT NULL,
    body_path TEXT NOT NULL,
    status TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    anchors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS personal_record_scope_updated_idx
    ON personal.record (domain, tenant_id, user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS personal.profile_context (
    domain TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    goals_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    preferences_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (domain, tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS ops.snapshot_pointer (
    layer TEXT NOT NULL,
    domain TEXT NOT NULL,
    current_snapshot_id TEXT NOT NULL,
    fact_snapshot_id TEXT NOT NULL,
    interpretation_snapshot_id TEXT,
    profile_version TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (layer, domain)
);

CREATE TABLE IF NOT EXISTS ops.snapshot_publication (
    snapshot_id TEXT NOT NULL,
    layer TEXT NOT NULL,
    domain TEXT NOT NULL,
    fact_snapshot_id TEXT NOT NULL,
    interpretation_snapshot_id TEXT,
    profile_version TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (snapshot_id, layer, domain)
);

CREATE INDEX IF NOT EXISTS ops_snapshot_publication_published_idx
    ON ops.snapshot_publication (domain, layer, published_at DESC);

CREATE TABLE IF NOT EXISTS ops.outbox_event (
    id BIGSERIAL PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    event_type TEXT NOT NULL,
    aggregate_layer TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ops_outbox_event_claim_idx
    ON ops.outbox_event (status, available_at, created_at);

CREATE INDEX IF NOT EXISTS ops_outbox_event_type_idx
    ON ops.outbox_event (event_type, status, available_at);

CREATE TABLE IF NOT EXISTS graph.dependency_edge (
    id BIGSERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    from_layer TEXT NOT NULL,
    from_id TEXT NOT NULL,
    to_layer TEXT NOT NULL,
    to_id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('shared', 'tenant', 'user')),
    tenant_id TEXT,
    user_id TEXT,
    edge_type TEXT,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS graph_dependency_edge_from_idx
    ON graph.dependency_edge (
        domain,
        from_layer,
        from_id,
        scope,
        tenant_id,
        user_id
    );

CREATE INDEX IF NOT EXISTS graph_dependency_edge_to_idx
    ON graph.dependency_edge (
        domain,
        to_layer,
        to_id,
        scope,
        tenant_id,
        user_id
    );

CREATE TABLE IF NOT EXISTS graph.rendered_page (
    id BIGSERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    layer TEXT NOT NULL,
    record_id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('shared', 'tenant', 'user')),
    tenant_id TEXT,
    user_id TEXT,
    path TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS graph_rendered_page_identity_key
    ON graph.rendered_page (
        domain,
        layer,
        record_id,
        scope,
        COALESCE(tenant_id, ''),
        COALESCE(user_id, '')
    );

CREATE INDEX IF NOT EXISTS graph_rendered_page_path_idx
    ON graph.rendered_page (path);
