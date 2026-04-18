# MCP Tool Contract Spec

## Purpose

This document defines a concrete MCP tool surface for a three-layer LLM Wiki MCP server.

The tool surface is designed to expose:

- shared Fact operations
- shared Interpretation operations
- user-scoped Personal operations
- graph and dependency inspection
- cache and snapshot visibility

The tools are intentionally provider-agnostic. Clients should not need to know which LLM vendor or internal storage technology was used.

## Design Goals

- keep tool contracts stable
- separate shared and user-scoped operations clearly
- make provenance and snapshot usage explicit
- expose invalidation state without leaking internal implementation details
- support bounded exploratory retrieval without exposing unrestricted datastore access
- support registered domain packs without redesigning the core protocol

## Tool Families

- source tools
- fact tools
- interpretation tools
- personal tools
- graph tools
- retrieval and exploration tools
- cache and snapshot tools
- admin tools

## Tool Design Principle

Tool contracts should prefer bounded operations over raw datastore access.

In particular:

- LLMs may need exploratory read access across graph and rendered wiki artifacts
- those reads should be exposed as constrained tools
- canonical Fact writes, dependency writes, and scope decisions should remain program-controlled

This allows agentic exploration without weakening integrity guarantees.

## Shared Request Fields

Most tools should support a common envelope where relevant.

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "scope": "shared"
}
```

Not every tool requires every field:

- shared tools often need only `domain`
- tenant-scoped tools need `tenant_id`
- personal tools require `user_id`

## Shared Response Fields

Derived and query-oriented tools should usually return:

```json
{
  "status": "ok",
  "provenance": {
    "fact_snapshot": "fact_snap_2026_04_15",
    "interpretation_snapshot": "interp_snap_2026_04_15",
    "profile_version": "profile_v7",
    "model_profile": "balanced_default"
  },
  "warnings": []
}
```

## Source Tools

### `list_sources`

List source records available from configured connectors.

Input:

```json
{
  "domain": "recruiting",
  "connector": "greenhouse",
  "updated_since": "2026-04-10T00:00:00Z",
  "limit": 100
}
```

Output:

```json
{
  "status": "ok",
  "items": [
    {
      "source_id": "greenhouse:job:abc123",
      "title": "Backend Engineer",
      "updated_at": "2026-04-15T08:00:00Z"
    }
  ]
}
```

### `fetch_source`

Fetch and normalize one source.

Input:

```json
{
  "domain": "recruiting",
  "source_id": "greenhouse:job:abc123"
}
```

Output:

```json
{
  "status": "ok",
  "record": {
    "source_id": "greenhouse:job:abc123",
    "connector": "greenhouse",
    "domain": "recruiting",
    "title": "Backend Engineer",
    "body_markdown": "Normalized markdown",
    "content_hash": "sha256:..."
  }
}
```

### `sync_sources`

Fetch a batch of updated sources and optionally persist raw snapshots.

Input:

```json
{
  "domain": "recruiting",
  "connector": "greenhouse",
  "updated_since": "2026-04-14T00:00:00Z",
  "persist_raw": true
}
```

Output:

```json
{
  "status": "ok",
  "fetched": 57,
  "persisted": 57,
  "source_ids": [
    "greenhouse:job:abc123"
  ]
}
```

## Fact Tools

### `ingest_fact_batch`

Ingest one or more normalized sources into the Fact layer.

Input:

```json
{
  "domain": "recruiting",
  "source_ids": [
    "greenhouse:job:abc123",
    "lever:posting:def456"
  ],
  "dedupe": true,
  "publish_snapshot": true
}
```

Output:

```json
{
  "status": "ok",
  "fact_snapshot": "fact_snap_2026_04_15_1200",
  "facts_created": 120,
  "facts_updated": 33,
  "facts_superseded": 2,
  "affected_fact_ids": [
    "job_posting_123",
    "company_42"
  ]
}
```

### `get_fact_record`

Return one canonical Fact record.

Input:

```json
{
  "domain": "recruiting",
  "fact_id": "job_posting_123"
}
```

Output:

```json
{
  "status": "ok",
  "record": {
    "id": "job_posting_123",
    "layer": "fact",
    "entity_type": "job_posting",
    "attributes": {},
    "relations": []
  }
}
```

### `search_facts`

Run structured or text-oriented Fact search.

Input:

```json
{
  "domain": "recruiting",
  "query": "backend tokyo startup python",
  "filters": {
    "entity_type": "job_posting"
  },
  "limit": 20
}
```

Output:

```json
{
  "status": "ok",
  "matches": [
    {
      "fact_id": "job_posting_123",
      "score": 0.93
    }
  ]
}
```

## Interpretation Tools

### `build_interpretation_snapshot`

Build or refresh a shared interpretation snapshot or family-level partition.

Input:

```json
{
  "domain": "recruiting",
  "partition": {
    "family": "market_trends",
    "segment": "backend_japan_midlevel"
  },
  "fact_snapshot": "fact_snap_2026_04_15_1200",
  "model_profile": "balanced_default",
  "publish": true
}
```

Output:

```json
{
  "status": "ok",
  "interpretation_snapshot": "interp_snap_2026_04_15_market_trends_backend_japan_midlevel",
  "records_created": 14,
  "records_updated": 6,
  "records_superseded": 2
}
```

### `get_interpretation_record`

Return one interpretation record.

Input:

```json
{
  "domain": "recruiting",
  "interpretation_id": "interp_123"
}
```

Output:

```json
{
  "status": "ok",
  "record": {
    "id": "interp_123",
    "kind": "trend",
    "claim": "Production LLM experience is increasingly preferred.",
    "confidence": 0.81,
    "evidence": [
      {
        "fact_id": "job_posting_123"
      }
    ]
  }
}
```

### `search_interpretations`

Search shared interpretation records.

Input:

```json
{
  "domain": "recruiting",
  "query": "Tokyo backend market trend",
  "filters": {
    "kind": "trend"
  },
  "limit": 20
}
```

Output:

```json
{
  "status": "ok",
  "matches": [
    {
      "interpretation_id": "interp_123",
      "score": 0.91
    }
  ]
}
```

### `render_interpretation_pages`

Render shared wiki pages from interpretation records or a snapshot partition.

Input:

```json
{
  "domain": "recruiting",
  "interpretation_snapshot": "interp_snap_2026_04_15_market_trends_backend_japan_midlevel",
  "page_family": "market_trend"
}
```

### `list_interpretation_proposals`

List non-published interpretation candidates for review or automated processing.

Input:

```json
{
  "domain": "recruiting",
  "partition": {
    "family": "market_trends",
    "segment": "backend_japan_midlevel"
  },
  "status": "proposed",
  "limit": 50
}
```

Output:

```json
{
  "status": "ok",
  "items": [
    {
      "proposal_id": "proposal_123",
      "interpretation_id": "interp_candidate_123",
      "review_state": "pending_validation"
    }
  ]
}
```

### `validate_interpretation_proposal`

Run validation on a proposed interpretation candidate.

Input:

```json
{
  "domain": "recruiting",
  "proposal_id": "proposal_123"
}
```

Output:

```json
{
  "status": "ok",
  "proposal_id": "proposal_123",
  "validation_state": "validated",
  "warnings": []
}
```

### `publish_interpretation_partition`

Publish a validated interpretation partition or staged candidate set.

Input:

```json
{
  "domain": "recruiting",
  "partition": {
    "family": "market_trends",
    "segment": "backend_japan_midlevel"
  },
  "source_state": "validated"
}
```

Output:

```json
{
  "status": "ok",
  "interpretation_snapshot": "interp_snap_2026_04_15_market_trends_backend_japan_midlevel",
  "published_records": 14
}
```

### `get_interpretation_proposal_status`

Return lifecycle and review status for one proposal.

Input:

```json
{
  "domain": "recruiting",
  "proposal_id": "proposal_123"
}
```

Output:

```json
{
  "status": "ok",
  "proposal_id": "proposal_123",
  "lifecycle_state": "validated",
  "review_state": "ready_to_publish"
}
```

Output:

```json
{
  "status": "ok",
  "pages_rendered": 4,
  "paths": [
    "wiki/shared/market/backend-japan-midlevel.md"
  ]
}
```

## Personal Tools

### `query_personal_knowledge`

Run a user-scoped query using the default retrieval flow:

- Personal
- Interpretation
- Fact

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "question": "What should I focus on to move into backend roles in Tokyo startups?",
  "profile_version": "profile_v7",
  "model_profile": "deep_synthesis",
  "save": false
}
```

Output:

```json
{
  "status": "ok",
  "answer_markdown": "## Strategy\n...",
  "personal_records_used": [
    "personal_plan_123"
  ],
  "interpretation_records_used": [
    "interp_123",
    "interp_220"
  ],
  "fact_records_used": [
    "job_posting_123"
  ],
  "provenance": {
    "fact_snapshot": "fact_snap_2026_04_15",
    "interpretation_snapshot": "interp_snap_2026_04_15",
    "profile_version": "profile_v7",
    "model_profile": "deep_synthesis"
  }
}
```

### `create_personal_plan`

Generate a new user-scoped plan, note, or strategy page.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "profile_version": "profile_v7",
  "kind": "career_transition_plan",
  "question": "Create a 12-week backend transition plan",
  "model_profile": "deep_synthesis"
}
```

Output:

```json
{
  "status": "ok",
  "personal_record_id": "personal_plan_123",
  "path": "wiki/users/user_42/plans/12-week-backend-transition.md",
  "anchors": [
    "interp_123",
    "interp_220",
    "fact_job_posting_999"
  ],
  "provenance": {
    "fact_snapshot": "fact_snap_2026_04_15",
    "interpretation_snapshot": "interp_snap_2026_04_15",
    "profile_version": "profile_v7"
  }
}
```

### `list_personal_records`

List user-scoped artifacts.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "kind": "career_transition_plan",
  "status": "active"
}
```

## Retrieval and Exploration Tools

These tools support bounded exploratory retrieval for LLM-driven workflows.

They should remain read-oriented or proposal-oriented and should not expose unrestricted writes to canonical stores.

### `search_personal_pages`

Search rendered personal wiki pages or personal document indexes.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "query": "weekly plan tokyo backend",
  "limit": 10
}
```

Output:

```json
{
  "status": "ok",
  "matches": [
    {
      "path": "wiki/users/user_42/plans/12-week-backend-transition.md",
      "score": 0.94
    }
  ]
}
```

### `search_interpretation_pages`

Search rendered shared interpretation pages or shared document indexes.

Input:

```json
{
  "domain": "recruiting",
  "query": "Tokyo startup backend trend",
  "limit": 10
}
```

Output:

```json
{
  "status": "ok",
  "matches": [
    {
      "path": "wiki/shared/market/backend-japan-midlevel.md",
      "score": 0.92
    }
  ]
}
```

### `query_markdown_index`

Query an optional markdown retrieval backend such as `qmd`.

Input:

```json
{
  "domain": "recruiting",
  "scope": "user",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "query": "career transition backend Tokyo",
  "collections": [
    "personal_pages",
    "shared_interpretation_pages"
  ],
  "limit": 10
}
```

Output:

```json
{
  "status": "ok",
  "matches": [
    {
      "path": "wiki/users/user_42/plans/12-week-backend-transition.md",
      "collection": "personal_pages",
      "score": 0.95
    }
  ]
}
```

### `explore_related_interpretations`

Run bounded graph exploration from an interpretation or subject anchor.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "start_node_id": "interp_123",
  "edge_types": [
    "supports",
    "contradicts",
    "refines"
  ],
  "max_hops": 2,
  "limit": 20
}
```

Output:

```json
{
  "status": "ok",
  "matches": [
    {
      "interpretation_id": "interp_220",
      "via_edge_type": "supports"
    }
  ]
}
```

### `get_evidence_facts`

Return evidence facts for one or more interpretation records.

Input:

```json
{
  "domain": "recruiting",
  "interpretation_ids": [
    "interp_123",
    "interp_220"
  ],
  "limit_per_interpretation": 10
}
```

Output:

```json
{
  "status": "ok",
  "items": [
    {
      "interpretation_id": "interp_123",
      "fact_ids": [
        "job_posting_123"
      ]
    }
  ]
}
```

### `propose_interpretation_update`

Submit a candidate interpretation, relation, or page update for validation and later publish.

Input:

```json
{
  "domain": "recruiting",
  "proposal_kind": "interpretation_update",
  "target_partition": {
    "family": "market_trends",
    "segment": "backend_japan_midlevel"
  },
  "content_markdown": "## Proposal\n...",
  "evidence_fact_ids": [
    "job_posting_123"
  ]
}
```

Output:

```json
{
  "status": "ok",
  "proposal_id": "proposal_123",
  "review_state": "pending_validation"
}
```

Output:

```json
{
  "status": "ok",
  "items": [
    {
      "personal_record_id": "personal_plan_123",
      "title": "12-week backend transition",
      "updated_at": "2026-04-15T13:00:00Z"
    }
  ]
}
```

## Graph Tools

### `get_graph_neighbors`

Return graph neighbors for a node with ACL and scope filtering applied.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "node_id": "interp_123",
  "edge_types": [
    "supports",
    "evidence_for",
    "anchored_to"
  ],
  "limit": 50
}
```

Output:

```json
{
  "status": "ok",
  "neighbors": [
    {
      "node_id": "fact_job_posting_999",
      "edge_type": "evidence_for"
    }
  ]
}
```

This tool is suitable for bounded exploration, but clients should prefer narrower retrieval tools where possible to reduce fan-out and improve debuggability.

### `get_dependency_impact`

Return downstream records that would be affected by a change.

Input:

```json
{
  "domain": "recruiting",
  "record_id": "job_posting_123",
  "record_type": "fact"
}
```

Output:

```json
{
  "status": "ok",
  "affected_interpretations": [
    "interp_123"
  ],
  "affected_rendered_pages": [
    "wiki/shared/market/backend-japan-midlevel.md"
  ],
  "affected_personal_records": [
    "personal_plan_123"
  ]
}
```

### `build_graph_artifacts`

Build graph artifacts for a snapshot tuple.

Input:

```json
{
  "domain": "recruiting",
  "fact_snapshot": "fact_snap_2026_04_15",
  "interpretation_snapshot": "interp_snap_2026_04_15",
  "scope": "shared"
}
```

Output:

```json
{
  "status": "ok",
  "graph_json": "graph/shared/recruiting/graph.json",
  "nodes": 4200,
  "edges": 11100
}
```

## Cache and Snapshot Tools

### `get_snapshot_status`

Return the currently published snapshot pointers for a domain or partition.

Input:

```json
{
  "domain": "recruiting",
  "partition": {
    "family": "market_trends"
  }
}
```

Output:

```json
{
  "status": "ok",
  "fact_snapshot": "fact_snap_2026_04_15",
  "interpretation_snapshot": "interp_snap_2026_04_15_market_trends",
  "published_at": "2026-04-15T12:30:00Z"
}
```

### `get_cache_status`

Inspect whether a record or answer cache is fresh, stale, or invalid.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "record_id": "personal_plan_123"
}
```

Output:

```json
{
  "status": "ok",
  "cache_state": "stale",
  "reason": "interpretation_refresh",
  "current_snapshots": {
    "fact_snapshot": "fact_snap_2026_04_15",
    "interpretation_snapshot": "interp_snap_2026_04_15"
  },
  "record_snapshots": {
    "fact_snapshot": "fact_snap_2026_04_14",
    "interpretation_snapshot": "interp_snap_2026_04_14"
  }
}
```

### `explain_result`

Explain why a result was produced or why it changed.

Input:

```json
{
  "domain": "recruiting",
  "result_id": "personal_plan_123"
}
```

Output:

```json
{
  "status": "ok",
  "explanation": {
    "based_on": {
      "fact_snapshot": "fact_snap_2026_04_15",
      "interpretation_snapshot": "interp_snap_2026_04_15",
      "profile_version": "profile_v7"
    },
    "anchors": [
      "interp_123",
      "fact_job_posting_999"
    ],
    "change_reason": "new interpretation snapshot"
  }
}
```

## Admin Tools

### `recompute_partition`

Force recomputation of a partition or family.

Input:

```json
{
  "domain": "recruiting",
  "layer": "interpretation",
  "partition": {
    "family": "market_trends",
    "segment": "backend_japan_midlevel"
  }
}
```

### `get_job_status`

Return status for a background job such as interpretation build, publish, graph rebuild, or cache refresh.

Input:

```json
{
  "job_id": "job_123"
}
```

Output:

```json
{
  "status": "ok",
  "job": {
    "job_id": "job_123",
    "state": "running",
    "kind": "interpretation_publish"
  }
}
```

Output:

```json
{
  "status": "ok",
  "job_id": "job_123"
}
```

### `mark_records_stale`

Mark selected records stale for background refresh.

Input:

```json
{
  "domain": "recruiting",
  "record_ids": [
    "personal_plan_123"
  ],
  "reason": "manual_refresh"
}
```

Output:

```json
{
  "status": "ok",
  "updated": 1
}
```

## Error Model

Every tool should return structured failures.

Example:

```json
{
  "error": {
    "code": "RECORD_NOT_FOUND",
    "message": "No interpretation record found for interp_123",
    "retryable": false
  }
}
```

Recommended error codes:

- `SOURCE_NOT_FOUND`
- `RECORD_NOT_FOUND`
- `SNAPSHOT_NOT_FOUND`
- `ACL_DENIED`
- `INVALID_SCOPE`
- `SCHEMA_VERSION_UNSUPPORTED`
- `PARTITION_LOCKED`
- `EXPLORATION_BUDGET_EXCEEDED`
- `TRAVERSAL_LIMIT_EXCEEDED`
- `REGENERATION_REQUIRED`
- `CACHE_INVALID`

## Domain Pack Extensibility

The core tool names should remain stable across domains.

Registered domain packs extend canonical behavior through:

- domain-specific schemas
- identity rules
- merge policies
- projection hints

Adjacent domain-owned modules may still extend behavior through:

- filter fields
- rendering templates
- interpretation builders

The client should not need a separate MCP contract for each domain.
