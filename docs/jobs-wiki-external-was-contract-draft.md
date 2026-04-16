# Jobs-Wiki External WAS Contract Draft

## Purpose

This document defines the minimum external contract that Jobs-Wiki WAS can safely depend on when delegating knowledge mutations outside the repository.

This document is boundary-first.

It does not define:

- MCP server internals
- database ownership
- schema ownership
- migration ownership
- ingestion implementation

Those concerns belong to the external provider boundary, not to Jobs-Wiki WAS.

## External Dependency Model

Jobs-Wiki should model two external dependencies, not one.

### 1. MCP Command Facade

Used for:

- command submission
- command status lookup
- authoritative mutation outcome reporting

Default path:

- WAS -> MCP command facade

### 2. Read Authority

The read authority is the external read-serving dependency whose responses the WAS treats as authoritative for user-visible knowledge state.

Important constraints:

- it may be one service or several services
- it is not assumed to be the same deployment surface as the MCP command facade
- the term does not imply that Jobs-Wiki owns the underlying database or schema

Default path:

- WAS -> read authority

## Core Boundary Rules

- read path and command path are separate
- frontend never talks to MCP directly
- polling is sufficient for v1
- command execution state and read-model visibility state are separate
- MCP may report read visibility only when it is authoritative for that projection
- if MCP is not authoritative for read visibility, it must return `pending`, `partial`, or `unknown` rather than guessing `applied`

## Minimum Command Surface

The minimum stable mutation contract for Jobs-Wiki is:

- `knowledge.object.upsert`
- `knowledge.object.archive`
- `knowledge.object.restore`
- `knowledge.relation.upsert`
- `knowledge.relation.remove`
- `knowledge.document.update`
- `knowledge.metadata.patch`
- `knowledge.command.get`

`knowledge.query.run` is intentionally excluded from the minimum fixed contract because it is too broad and risks collapsing the read path into the command path.

## Command and Read-Visibility States

### Command Execution State

- `accepted`
- `validating`
- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

### Read-Model State

- `applied`
- `pending`
- `partial`
- `unknown`
- `stale`
- `not_applicable`

Rule:

- `succeeded` means the command completed successfully
- `applied` means a specific read projection is authoritatively visible
- these states must never be collapsed into one field

## Projection Definition

A projection is a user-visible read shape derived from canonical knowledge objects and/or canonical relations for a specific presentation purpose.

Projection rules:

- a projection is not automatically a canonical object
- projections may lag behind command execution
- read visibility should be tracked per projection family, not globally

The minimum projection families that Jobs-Wiki should recognize are:

- `tree`
- `document`
- `graph`
- `calendar`
- `search`
- `workspace_summary`

## Current Rendered Page Read Contract

The current StrataWiki page-read entrypoint is narrower than the full read
authority space described in this draft.

Today it is authoritative only for rendered `document` projection reads over:

- Personal pages
- shared Interpretation pages

The minimum response contract for this slice should therefore be:

```json
{
  "ok": true,
  "projection": {
    "family": "document",
    "layer": "personal",
    "scope": "user"
  },
  "read_model_state": "applied",
  "page": {
    "record_id": "personal:plan-1"
  }
}
```

For a missing page, the contract should still report the projection as
authoritatively checked:

```json
{
  "ok": false,
  "projection": {
    "family": "document",
    "layer": "personal",
    "scope": "user"
  },
  "read_model_state": "applied",
  "error": {
    "code": "page_not_found"
  }
}
```

Current rules for this slice:

- `page_not_found` is not the same as `not_applicable`
- `not_applicable` should not be emitted unless the read authority can
  authoritatively prove that the requested projection family is outside its
  supported surface
- projection metadata should identify at least `family`, `layer`, and `scope`
- richer states such as `pending`, `partial`, `unknown`, and `stale` should
  remain out of this page-read contract until the implementation can detect them

## Current Retrieval Candidate Read Contract

The current StrataWiki retrieval path is now also exposed through a narrow
read-authority contract, but it remains candidate-oriented rather than
answer-oriented.

Today this slice is authoritative only for layered candidate resolution over the
current rendered/read model.

The minimum response contract for this slice should therefore be:

```json
{
  "ok": true,
  "projection": {
    "family": "retrieval",
    "scope": "user",
    "layers": [
      "personal",
      "interpretation",
      "fact"
    ]
  },
  "read_model_state": "applied",
  "retrieval": {
    "personal_ids": [
      "personal:plan-1"
    ],
    "interpretation_ids": [
      "interp:market-1"
    ],
    "fact_ids": [
      "fact:job-1"
    ],
    "personal_pages": [
      {
        "record_id": "personal:plan-1",
        "title": "Backend transition plan",
        "path": "wiki/personal/tenant-a/user-42/plan-1.md"
      }
    ],
    "snapshot_ref": {
      "fact_snapshot_id": "fact_snap_2026_04_16",
      "interpretation_snapshot_id": "interp_snap_2026_04_16",
      "profile_version": "profile_v7"
    }
  }
}
```

Current rules for this slice:

- this contract is authoritative for candidate resolution, not final synthesized
  answers
- `read_model_state` remains `applied` because richer retrieval visibility state
  is not yet implemented
- `projection.layers` should state the actual retrieval order used by the slice
- grouped ids remain the stable identity output
- grouped page summaries are also available for direct consumer hydration of
  title/path/snapshot metadata without a second lookup
- grouped retrieval-facing record summaries may also be included per layer as
  optional `personal_records`, `interpretation_records`, and `fact_records`
- grouped retrieval explanations may also be included per layer as optional
  `personal_explanations`, `interpretation_explanations`, and
  `fact_explanations`
- these are intentionally narrower than full canonical storage envelopes
- these hydrated summaries strengthen the pre-generation contract but still do
  not imply synthesized answer generation

## Current Personal Answer Read Contract

The current StrataWiki personal query path is now wider than retrieval-candidate
reads and should be treated as a distinct answer projection.

Today this slice is authoritative for user-scoped answer assembly over the
current retrieval/read model.

The minimum response contract for this slice should therefore be:

```json
{
  "ok": true,
  "projection": {
    "family": "answer",
    "kind": "personal_query",
    "scope": "user",
    "layers": [
      "personal",
      "interpretation",
      "fact"
    ]
  },
  "read_model_state": "applied",
  "answer": {
    "answer_type": "personal_query_answer",
    "generation_strategy": "deterministic_summary_bundle_v1",
    "answer_markdown": "# Personal Knowledge Answer"
  },
  "retrieval": {
    "personal_ids": [
      "personal:plan-1"
    ]
  }
}
```

Current rules for this slice:

- this contract is authoritative for answer projection, not only candidate
  retrieval
- it is still layered on top of `retrieve_for_query` as a lower-level primitive
- `projection.kind` should distinguish the answer slice from future non-personal
  answer shapes
- `generation_strategy` should make the current answer assembly mode explicit
  when the implementation is deterministic or otherwise strategy-bound
- `answer_rationale` may be included as a user-facing explanation of why the
  current context bundle was selected
- the underlying `retrieval` payload may still be returned for explainability
  and consumer debugging

## Recommended Refresh Scope Vocabulary

Command results should return both:

- `affectedObjectRefs`
- `recommendedRefreshScopes`

The minimum stable refresh-scope vocabulary is:

- `tree`
- `document`
- `graph_neighborhood`
- `calendar`
- `search`
- `workspace_summary`

Example payloads:

```json
{"scopeType": "tree", "workspaceId": "ws_jobs_001"}
```

```json
{"scopeType": "document", "objectId": "doc_resume_strategy"}
```

```json
{"scopeType": "graph_neighborhood", "centerId": "doc_resume_strategy", "depth": 1}
```

```json
{"scopeType": "calendar", "workspaceId": "ws_jobs_001", "rangeStart": "2026-04-01", "rangeEnd": "2026-04-30"}
```

```json
{"scopeType": "search", "workspaceId": "ws_jobs_001", "reason": "reindex_needed"}
```

```json
{"scopeType": "workspace_summary", "workspaceId": "ws_jobs_001"}
```

## Document and Metadata Boundary

Jobs-Wiki should keep document-surface edits separate from canonical structured metadata edits.

### `knowledge.document.update`

Use for the authored document surface:

- `title`
- `bodyMarkdown`
- document-surface presentational fields

### `knowledge.metadata.patch`

Use for canonical structured metadata:

- `tags`
- lifecycle `status`
- `dueAt`
- source metadata
- structured user annotations

### Frontmatter Rule

Frontmatter-like fields should not be classified by markdown placement.

Instead:

- document-surface fields belong to `document.update`
- canonical structured fields belong to `metadata.patch`

This preserves stable semantics across markdown and structured JSON representations.

## Relation Contract

Relations should expose stable `relationId` values.

Rules:

- relation create may omit `relationId`
- relation update must include `relationId`
- relation remove must include `relationId`
- `(relationType, fromId, toId)` may be used as a lookup hint on create, but not as authoritative identity for update or remove

### Relation Provenance

Explicit and derived relations should remain distinguishable.

Minimum stable provenance classes:

- `explicit_command`
- `derived_from_document`

Recommended default exposure:

- include provenance on graph detail and document detail reads
- do not require it on every list or search response

## Archive and Restore

Archive is a logical lifecycle transition, not:

- hard delete
- upstream source deletion
- ACL mutation

Archive policy:

- archived objects remain addressable by ID
- they may be hidden by default in tree, search, calendar, and graph reads
- restore should be part of the minimum lifecycle surface

Archive should not be assumed to apply uniformly to every object class.

Recommended object-class policy:

- user-authored objects: archive + restore supported
- imported/source-backed objects: archive usually means local suppression or hide
- system-derived objects: archive is usually not the primary control surface

## Projection-Local Visibility

Read visibility should be projection-local, not global.

Recommended projection-local state shape:

```json
{
  "projectionStatus": [
    {"projection": "document", "state": "applied", "version": "docv_104"},
    {"projection": "graph", "state": "pending"},
    {"projection": "search", "state": "applied", "version": "searchv_88"}
  ]
}
```

Minimum version-carrying subset for v1:

- `document`
- `graph`
- `search`
- `calendar`

## Canonical Objects vs Projection-Only Structures

Use this classification rule:

- canonical object if it has stable identity and can be directly targeted by lifecycle or edit commands
- projection-only if it exists only as a view shape for presentation, traversal, ranking, or aggregation

Recommended classification:

- `folder`: projection-only unless Jobs-Wiki later introduces user-managed folder objects
- `calendar_event`: canonical only if explicitly modeled as a first-class scheduled object
- `search_hit`: projection-only
- `graph_node`: projection-only wrapper around canonical object references
- `graph_edge`: projection-only wrapper around canonical relation references
- `tag`: canonical object if given stable identity and lifecycle; otherwise projection-only label
- `workspace_summary_card`: projection-only

## WAS Behavior Guidance

Default WAS behavior by read-model state:

- `applied`: refresh immediately for that projection
- `pending`: keep last-known data and mark syncing
- `partial`: refresh only applied projections and keep last-known data for the rest
- `unknown`: keep last-known data and avoid claiming freshness
- `stale`: keep last-known data if usable and mark stale until refreshed

## Fixed Now vs Draft

### Fix Now

- `read authority` terminology
- separation of read path and command path
- minimum mutation command set
- separate command state and read-model state
- projection definition
- minimum refresh-scope vocabulary
- `document.update` vs `metadata.patch` boundary
- stable `relationId`
- relation provenance classes
- archive as logical lifecycle state with restore
- projection-local visibility reporting

### Keep Draft

- exact projection version format
- exact archive applicability for every imported object class
- richer provenance fields beyond the minimum classes
- future artifact-generation commands
- event stream or webhook support beyond polling
