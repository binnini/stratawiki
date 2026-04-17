# Jobs-Wiki External MCP Command Contract Draft

## Context

Jobs-Wiki is treating the MCP server as an external knowledge backend boundary, not as an in-repo implementation target.

The important constraints for this draft are:

- Jobs-Wiki WAS is the user-facing web service
- MCP-based clients are external consumers from the WAS point of view
- MCP server implementation, DB ownership, schema, and migrations are outside the Jobs-Wiki repo
- ingestion is separate from WAS
- WAS delegates edit and query requests across an external MCP boundary
- this design should stay command-oriented and boundary-first

Relevant existing repository direction already favors:

- explicit service boundaries over DB coupling to WAS
- asynchronous projection and stale marking
- snapshot-aware consistency instead of pretending all layers are globally transactional

## Current Question

What external MCP contract should Jobs-Wiki WAS rely on so it can safely delegate knowledge edits and queries without depending on MCP internals?

## Observations

- A file-centric protocol is too weak for multi-object, relation-aware, eventually consistent knowledge updates.
- WAS needs a stable command boundary, not direct exposure to outbox, workers, queues, or DB state.
- `accepted`, `executed`, and `visible in current read model` are different states and should not be collapsed.
- `affectedObjectIds` alone is insufficient for efficient UI refresh because a PKM-like workspace also needs refresh hints for graph, document, search, and calendar projections.
- Relation edits should remain explicit commands or explicit sub-operations rather than being hidden inside freeform document updates.
- Markdown and structured updates can share one command envelope, but not by collapsing into an opaque patch blob. Intent must remain typed.

## Options

- File-only or markdown-only edit protocol with weak typing.
- Free-edit session protocol where MCP interprets arbitrary edit instructions.
- Command-oriented contract with typed intents, asynchronous status, and refresh guidance.

## Decision or Working Direction

Prefer the third option.

Working contract direction:

- WAS calls MCP through a command-oriented API
- every mutation request creates a durable command resource with idempotency semantics
- command result separates execution outcome from read-model visibility
- MCP returns both affected object references and recommended refresh scopes
- query operations remain query-shaped, but mutation and refresh-triggering operations are command-shaped

Recommended minimum command families:

- `knowledge.object.upsert`
- `knowledge.object.archive`
- `knowledge.relation.upsert`
- `knowledge.relation.remove`
- `knowledge.document.update`
- `knowledge.metadata.patch`
- `knowledge.query.run`
- `knowledge.command.get`

Recommended status split:

- command processing status: `accepted | validating | queued | running | succeeded | failed | cancelled`
- read-model application status: `unknown | pending | partial | applied | stale | not_applicable`

Boundary rule:

- MCP decides whether the command itself succeeded
- MCP also reports what it knows about downstream read-model application
- WAS decides only how to present that state to the user

Refresh guidance should include both:

- `affected_object_refs`
- `recommended_refresh_scopes`

The refresh scopes are important for the Jobs-Wiki UI because the user may currently be in:

- file tree / document reader
- graph view
- calendar view
- search result view
- workspace dashboard or activity feed

## Open Questions

- Whether `knowledge.document.update` should allow inline relation operations in one request or require separate sibling commands inside a batch envelope.
- Whether event stream subscription should be added after polling is stable, or whether a webhook/event bridge is better for WAS.
- How much temporal projection information should be returned in v1 for calendar refresh without overcommitting backend internals.
- Whether future query APIs should expose backend-composed graph or temporal projections directly, or allow WAS to compose more of them.

## Next Actions

- Keep the mutation contract command-oriented and asynchronous by default.
- Fix the minimal envelope, lifecycle fields, error taxonomy, and idempotency rule now.
- Keep `recommended_refresh_scopes`, read-model lag details, and event-stream support as draft/candidate areas, but reserve field names now.
- Do not freeze a file-only or free-edit protocol for v1.

## Clarifications Added

### MCP vs Knowledge Backend Ownership

For Jobs-Wiki, the safest external dependency is:

- WAS -> MCP for mutation commands and command status
- WAS -> read backend for normal read APIs

This means MCP should be modeled as a command boundary, not automatically as the entire read-serving backend.

Reason:

- it avoids forcing Jobs-Wiki to assume one deployment shape behind the external system
- it keeps command acceptance/execution separate from read serving
- it prevents the WAS contract from depending on whether read models are served by the same process, another service, or a gateway

If the external provider later chooses to unify command handling and read serving behind one endpoint, that remains their implementation detail.

### Authoritative Read Visibility Rule

`readModelState = applied` is only trustworthy when the MCP-facing contract can authoritatively observe that the targeted projection version is published and readable.

If the command facade cannot observe read publication directly, it should not guess. In that case it should return:

- `pending`
- `partial`
- or `unknown`

and include projection-specific visibility information only where authoritative.

### Query Boundary

`knowledge.query.run` should not be fixed in the minimum mutation contract yet.

The name is too broad and risks collapsing:

- transient semantic querying
- artifact-producing generation
- ordinary read retrieval

For Jobs-Wiki v1, normal reads should stay on the WAS read path, not on the command path. If a future command creates durable query artifacts, it should be modeled explicitly as an artifact-generation command rather than a generic query primitive.

### Object vs Document Commands

`knowledge.object.upsert` is the generic command for structured object creation or replacement.

`knowledge.document.update` is a document-specific mutation command for body-oriented edits with document-level concurrency semantics.

Recommended v1 rule:

- keep `knowledge.document.update`
- keep `knowledge.object.upsert`
- use `document.update` for markdown/body/title edits on document objects
- use `object.upsert` for non-document objects or full structured object writes

This preserves a clean knowledge-object model without pretending every object has document-like edit semantics.

### Relation Identity

Prefer stable `relationId` values.

The tuple `(relationType, fromId, toId)` is not enough once relation attributes, provenance, temporal intervals, confidence, or multiple parallel edges become relevant.

The tuple may still be used as a uniqueness key for specific relation classes if the external provider wants that internally, but the external contract should expose stable `relationId`.

### Link Extraction Rule

For graph correctness and retry safety, relation mutation should remain explicit in the external contract.

If an external backend chooses to derive link relations from document content, those relations should be marked as derived provenance, not merged invisibly with explicitly commanded relations.

### Version Scope

`publishedReadModelVersion` should not be modeled as one global version.

The most useful contract shape is projection-local version visibility, for example:

- document projection version
- graph projection version
- search projection version
- calendar projection version
- workspace summary projection version

This is enough for the WAS to explain sync state without binding to internal worker or DB mechanics.

### Read-Side Naming

For Jobs-Wiki docs, prefer the term `read authority`.

Definition:

- the external read-serving dependency whose responses the WAS treats as authoritative for user-visible knowledge state
- it may be backed by one service or several services
- it is not assumed to be the same deployment surface as the MCP command facade
- it defines the externally visible read semantics Jobs-Wiki depends on without implying DB ownership by Jobs-Wiki

### Projection Definition

A projection is a user-visible read shape derived from canonical knowledge objects and/or canonical relations for a presentation purpose.

Boundary rules:

- a projection is not automatically a canonical object
- a projection may lag behind command execution
- projection visibility is tracked per projection family, not globally

Recommended projection families:

- `tree`: mixed object-derived and aggregate-derived navigation structure
- `document`: primarily object-derived with optional relation-derived decoration
- `graph`: mixed relation-derived and object-derived neighborhood view
- `calendar`: primarily temporal-derived view
- `search`: mixed object-derived, relation-derived, and retrieval-index-derived view
- `workspace_summary`: aggregate-derived summary view

### Document vs Metadata Boundary

Strict v1 rule:

`knowledge.document.update` is for the authored document surface:

- `title`
- `bodyMarkdown`
- document-surface presentational fields

`knowledge.metadata.patch` is for canonical structured metadata:

- `tags`
- lifecycle `status`
- `dueAt`
- source metadata
- structured user annotations

Recommended treatment for frontmatter-like fields:

- do not treat raw frontmatter as contract authority
- classify each field by meaning, not by markdown placement
- document-surface fields belong to `document.update`
- canonical structured fields belong to `metadata.patch`

This preserves stable semantics across markdown and structured JSON forms.

### Archive Applicability

Archive/restore should not be assumed to apply uniformly to every object class.

Recommended policy:

- user-authored objects: archive + restore supported
- imported or source-backed objects: archive is object-class specific and usually means local hide/suppress, not source deletion
- system-derived objects: archive is usually not the primary lifecycle action; regeneration or invalidation is preferred

### Canonical Objects vs Projection-Only Structures

Use this rule:

- canonical object if it has stable identity and can be directly targeted by lifecycle or edit commands
- projection-only if it exists only as a view shape for presentation, traversal, ranking, or aggregation

Recommended classification:

- `tag`: canonical object
- `calendar_event`: canonical only if modeled as a first-class scheduled object; otherwise projection-only
- `folder`: projection-only unless Jobs-Wiki explicitly introduces user-managed folder objects
- `graph_node`: projection-only wrapper around canonical object references
- `graph_edge`: projection-only wrapper around canonical relation references
- `search_hit`: projection-only
- `workspace_summary_card`: projection-only
