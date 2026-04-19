# MCP Tool Contract Spec

## Purpose

This document defines the MCP tool surface for a three-layer LLM Wiki MCP server.

The tool surface is designed to expose:

- shared Fact operations
- shared Interpretation operations
- user-scoped Personal operations
- graph and dependency inspection
- cache and snapshot visibility

The tools are intentionally provider-agnostic. Clients should not need to know which LLM vendor or internal storage technology was used.

This document distinguishes between:

- the currently implemented Week 1 MVP tool surface
- the broader target tool surface that the architecture is designed to grow into

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

## Current Implemented Tool Surface

The repository currently exposes these runtime tools:

- `ingest_fact_batch`
- `validate_domain_proposal_batch`
- `ingest_domain_proposal_batch`
- `get_fact_record`
- `build_interpretation_snapshot`
- `get_interpretation_record`
- `list_interpretation_proposals`
- `validate_interpretation_proposal`
- `publish_interpretation_partition`
- `get_interpretation_proposal_status`
- `upsert_profile_context`
- `query_personal_knowledge`
- `get_snapshot_status`
- `get_cache_status`
- `get_job_status`
- `explain_result`

Current MVP caveats:

- external integration clients should prefer `validate_domain_proposal_batch` and `ingest_domain_proposal_batch`
- `ingest_fact_batch` remains available as a legacy transition path for source-driven or internal flows
- `ingest_fact_batch` currently accepts inline `source_records` rather than source ids fetched from external connectors
- `build_interpretation_snapshot` still requires explicit `fact_ids` on the happy path
- `build_interpretation_snapshot` now accepts `execution_mode: "background"` to queue worker execution, but broader async job families remain follow-up work
- interpretation proposal lifecycle is now operator-visible through list, validate, publish, and status tools
- `publish_interpretation_partition` currently iterates the matching shared partition candidates and can return `status: "partial"` if one candidate publishes while another fails lifecycle checks
- `query_personal_knowledge` now has a runtime-owned profile provisioning path through `upsert_profile_context`
- `get_snapshot_status` now returns the per-layer registry when called with only `domain`, while partition-filtered calls still return the interpretation layer pointer
- `get_cache_status` currently inspects saved Personal outputs by comparing their stored snapshot tuple against the current published snapshot tuple and current profile version
- `get_job_status` currently reports runtime-owned outbox jobs, starting with interpretation build requests
- `explain_result` currently explains shared Interpretation results and saved Personal outputs; broader rendered-page and graph explainability remains follow-up work
- the Domain Proposal tools are implemented even though they were not part of the original narrow Week 1 MVP tool list

### Current External Write Guidance

The current preferred external write contract is `DomainProposalBatch`.

Recommended sequence:

1. load or configure the active Domain Pack for the target domain
2. call `validate_domain_proposal_batch`
3. call `ingest_domain_proposal_batch`

The repository keeps `ingest_fact_batch` for transition and internal source-driven paths, but external producers should not treat it as the default write surface.

### Current Long-Lived Runtime Boundary

The current intended long-lived runtime contract is a StrataWiki-managed stdio process.

Start it with:

```bash
stratawiki serve
```

or equivalently:

```bash
python -m wiki_mcp.cli serve
```

This is not full JSON-RPC.
It is a repository-owned newline-delimited JSON contract that lets external clients keep one StrataWiki runtime process open instead of shelling out for each tool call.

Request envelope:

```json
{
  "id": "req-1",
  "method": "call_tool",
  "params": {
    "name": "get_snapshot_status",
    "arguments": {
      "domain": "recruiting"
    }
  }
}
```

Response envelope:

```json
{
  "id": "req-1",
  "ok": true,
  "protocol_version": "2026-04-19",
  "result": {
    "status": "ok"
  }
}
```

Error envelope:

```json
{
  "id": "req-1",
  "ok": false,
  "protocol_version": "2026-04-19",
  "error": {
    "code": "tool_error",
    "message": "Unknown tool: ...",
    "details": {
      "type": "KeyError"
    }
  }
}
```

Supported runtime methods today:

- `health`
- `list_tools`
- `show_tool`
- `call_tool`
- `shutdown`

Ownership rules for this boundary:

- external clients talk to the runtime process, not to Postgres directly
- StrataWiki owns canonical DB access, rendering side effects, snapshot state, and model-provider credentials
- external clients own request sequencing and payload construction
- `call_tool` should be used with the same input shapes documented for the current implemented tool surface

### Current Background Build Guidance

The first worker-compatible background path is interpretation build execution.

Recommended sequence:

1. call `build_interpretation_snapshot` with `execution_mode: "background"`
2. let the StrataWiki worker claim the queued request
3. inspect worker results and snapshot status through the canonical runtime

Current baseline:

- the queue carrier is the runtime-owned outbox repository
- the worker entrypoint is `stratawiki worker`
- only queued interpretation build requests are handled by this first worker path
- broader scheduler and multi-job orchestration remain planned follow-up work

## Planned Tool Surface

The remaining sections describe the broader target protocol shape.
They should be read as design targets unless a tool is explicitly listed above as currently implemented.

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

Current contract note:

- implemented
- not the preferred external write path for integration clients
- retained for transition and internal source-driven use

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

### `validate_domain_proposal_batch`

Validate one `DomainProposalBatch` against the active Domain Pack without committing writes.

Input:

```json
{
  "batch": {
    "domain": "recruiting",
    "pack_version": "2026-04-18",
    "producer": "jobs-wiki",
    "facts": [
      {
        "proposal_id": "fact:posting:EMP-1",
        "domain": "recruiting",
        "entity_type": "job_posting",
        "attributes": {
          "title": "Backend Engineer"
        },
        "identity_hints": {
          "source_id": "EMP-1"
        },
        "evidence": [
          {
            "connector": "worknet",
            "source_id": "EMP-1"
          }
        ]
      }
    ]
  }
}
```

Output:

```json
{
  "ok": true,
  "committed": false,
  "dry_run": true,
  "audit": {
    "evaluated_pack_version": "2026-04-18"
  },
  "write_plan": {
    "facts_to_create": 1,
    "facts_to_update": 0,
    "facts_to_noop": 0,
    "relations_to_create": 0
  }
}
```

### `ingest_domain_proposal_batch`

Commit one validated `DomainProposalBatch` through the canonical proposal gateway.

Input:

```json
{
  "batch": {
    "domain": "recruiting",
    "pack_version": "2026-04-18",
    "producer": "jobs-wiki",
    "facts": [
      {
        "proposal_id": "fact:posting:EMP-1",
        "domain": "recruiting",
        "entity_type": "job_posting",
        "attributes": {
          "title": "Backend Engineer"
        },
        "identity_hints": {
          "source_id": "EMP-1"
        },
        "evidence": [
          {
            "connector": "worknet",
            "source_id": "EMP-1"
          }
        ]
      }
    ]
  }
}
```

Output:

```json
{
  "ok": true,
  "committed": true,
  "fact_snapshot_id": "fact_snap_2026_04_15_1200",
  "facts_created": 1,
  "facts_updated": 0,
  "relations_created": 0,
  "affected_fact_ids": [
    "fact:job_posting:EMP-1"
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
      "lifecycle_state": "proposed",
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
  "ok": true,
  "validation_state": "validated",
  "review_state": "ready_to_publish",
  "errors": []
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
  "published_records": 1,
  "published_proposal_ids": ["proposal_123"],
  "superseded_ids": []
}
```

Current MVP note:

- the first implementation publishes shared-scope partition candidates one proposal at a time using the existing interpretation publication service
- if one candidate fails after another already published, the tool reports `status: "partial"` with a `failures` list instead of pretending the whole partition succeeded atomically

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
  "review_state": "ready_to_publish",
  "family": "market_trend",
  "subject_id": "backend_japan_midlevel"
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

### `upsert_profile_context`

Create or update the stored profile context required for later Personal query calls.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "profile_version": "profile_v7",
  "goals": [
    "move into backend roles in Tokyo startups"
  ],
  "preferences": {
    "location": "tokyo"
  },
  "attributes": {
    "level": "mid"
  }
}
```

Output:

```json
{
  "status": "ok",
  "profile_context": {
    "domain": "recruiting",
    "tenant_id": "tenant_a",
    "user_id": "user_42",
    "profile_version": "profile_v7",
    "goals": [
      "move into backend roles in Tokyo startups"
    ],
    "preferences": {
      "location": "tokyo"
    },
    "attributes": {
      "level": "mid"
    }
  }
}
```

### `query_personal_knowledge`

Run a user-scoped query using the default retrieval flow:

- Personal
- Interpretation
- Fact

Current contract note:

- clients should provision the matching stored profile first through `upsert_profile_context`
- the requested `profile_version` must still match the current stored profile context exactly

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
  "layers": {
    "fact": {
      "fact_snapshot_id": "fact_snap_2026_04_15",
      "current_snapshot_id": "fact_snap_2026_04_15",
      "published_at": "2026-04-15T12:00:00Z"
    },
    "interpretation": {
      "fact_snapshot_id": "fact_snap_2026_04_15",
      "interpretation_snapshot_id": "interp_snap_2026_04_15_market_trends",
      "current_snapshot_id": "interp_snap_2026_04_15_market_trends",
      "published_at": "2026-04-15T12:30:00Z"
    }
  }
}
```

Current MVP note:

- `domain` only returns a domain-level snapshot registry with one entry per published layer
- `partition.family` still narrows the lookup to the interpretation layer; true partition-granular snapshot registries remain follow-up work

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
  "reason": "interpretation_snapshot_changed",
  "current_snapshots": {
    "fact_snapshot": "fact_snap_2026_04_15",
    "interpretation_snapshot": "interp_snap_2026_04_15",
    "profile_version": "profile_v7"
  },
  "record_snapshots": {
    "fact_snapshot": "fact_snap_2026_04_14",
    "interpretation_snapshot": "interp_snap_2026_04_14",
    "profile_version": "profile_v6"
  }
}
```

Current MVP note:

- the implemented cache inspection path is currently for saved Personal outputs only
- missing records return `cache_state: "missing"`
- `profile_version` drift is treated as `invalid`
- broader retrieval, graph, and rendered-page cache families remain follow-up work

### `explain_result`

Explain why a result was produced or why it changed.

Input:

```json
{
  "domain": "recruiting",
  "layer": "personal",
  "tenant_id": "tenant-1",
  "user_id": "user-1",
  "result_id": "personal_plan_123"
}
```

Output:

```json
{
  "status": "ok",
  "layer": "personal",
  "result_id": "personal_plan_123",
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
    "change_reason": "interpretation_snapshot_changed",
    "cache_state": "stale"
  }
}
```

Current MVP note:

- `layer` may be `personal` or `interpretation`
- Personal explanations currently require `tenant_id` and `user_id`
- Personal explanations reuse the same snapshot drift reasons as `get_cache_status`
- Interpretation explanations currently summarize lifecycle state, current published partition ids, evidence-backed anchors, and snapshot drift against the current shared registry

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
    "state": "processed",
    "kind": "interpretation_build",
    "event_type": "interpretation_snapshot_build_requested"
  }
}
```

Current MVP note:

- the first implementation reads the runtime-owned outbox store directly
- it currently reports queued or processed interpretation build jobs
- broader job families will show up here as the worker surface expands

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
