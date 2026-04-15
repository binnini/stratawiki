# LLM Wiki Pattern Adapted for StrataWiki

## Purpose

This document explains how the original LLM Wiki pattern should be adapted for StrataWiki.

The original pattern is valuable because it captures a core idea that still matters:

knowledge should compound over time rather than be rediscovered from raw documents on every query.

However, StrataWiki is not a direct copy of the original markdown-only wiki pattern.

StrataWiki introduces:

- multi-user operation
- tenant and user scope boundaries
- canonical Fact storage
- canonical Interpretation storage
- Personal overlays
- graph-based dependency routing
- explicit snapshots, caching, and invalidation

This means the original pattern must be preserved in spirit but changed in structure.

## The Original Insight That Still Holds

The most important idea in the original LLM Wiki pattern is this:

A system should not rely on raw retrieval alone if the same synthesis, contradiction detection, and cross-linking work must be repeated over and over.

Instead, it should create and maintain a persistent knowledge artifact that becomes richer over time.

This remains true in StrataWiki.

The system should still:

- accumulate knowledge incrementally
- preserve prior synthesis
- surface contradictions earlier rather than later
- turn valuable answers into durable artifacts
- reduce repeated cognitive work for both user and model

## The Main Structural Change

The original pattern can be summarized as:

- raw sources
- wiki
- schema instructions

StrataWiki changes that into:

- raw source snapshots
- Fact canonical layer
- Interpretation canonical layer
- Personal layer
- rendered wiki views
- MCP tool contracts and design docs

This is the key adaptation.

### Original Pattern

The wiki itself was the central knowledge substrate.

### StrataWiki Pattern

The wiki becomes the readable layer of a larger knowledge system.

That means:

- canonical truth is not stored only in markdown
- markdown remains important, but as a rendered artifact
- the system needs storage and state models that support multi-user operation

## What StrataWiki Keeps from the Original Pattern

### 1. Knowledge Should Compound

This remains central.

StrataWiki should avoid re-deriving the same market insight, contradiction, or personal strategy context from scratch on every query.

Instead:

- Facts accumulate
- Interpretations are refreshed and reused
- Personal outputs can build on prior work

### 2. Ingest, Query, Lint Remain Core Operations

The original workflow loop is still valid.

In StrataWiki:

- `Ingest` becomes source normalization and Fact publication
- `Query` becomes Personal-first retrieval over Personal, Interpretation, and Fact
- `Lint` becomes system health checking over stale views, contradictions, missing links, schema drift, and dependency integrity

### 3. Answers Should Become Artifacts

A good answer should not disappear into chat history.

In StrataWiki, good outputs can become:

- Personal strategy pages
- shared rendered interpretation pages
- promoted documentation
- reusable analysis artifacts

This is still one of the strongest ideas in the original pattern.

### 4. Human Curates, LLM Maintains

This also still holds.

The human should remain responsible for:

- choosing domains
- setting goals
- deciding what matters
- reviewing important decisions
- supplying or approving sources

The LLM should remain responsible for:

- extraction support
- synthesis drafts
- cross-reference suggestions
- page maintenance
- stale-marking suggestions
- promotion candidates for official docs

### 5. Readable Knowledge Artifacts Still Matter

Even though markdown is no longer the only source of truth, readable artifacts remain valuable.

Users and developers still benefit from:

- browsing shared interpretations
- reviewing personal plans in markdown form
- reading synthesized summaries without querying raw storage directly

## What StrataWiki Must Change

### 1. Markdown Is Not the Only System of Record

This is the largest change.

In the original pattern, the wiki itself is the maintained knowledge base.

In StrataWiki:

- Fact is canonical observed data
- Interpretation canonical is structured derived data
- Personal metadata is structured operational state
- markdown is the readable rendering layer

If markdown is treated as the only source of truth, StrataWiki will inherit avoidable problems:

- poor concurrency handling
- weak invalidation
- duplication of shared content
- poor ACL boundaries
- token inefficiency
- weak dependency routing

### 2. Raw Sources Must Become Versioned Snapshots

The original pattern speaks of immutable raw sources.

In StrataWiki, the useful adaptation is:

- raw inputs are stored as versioned snapshots
- source systems may change over time
- provenance and snapshot versioning matter more than naive immutability

This is especially important when using APIs or dynamic external systems.

### 3. The Schema Is No Longer One File

The original pattern uses a schema file such as `AGENTS.md` as the operational contract.

In StrataWiki, that role is distributed across:

- architecture docs
- data model specs
- MCP tool contracts
- domain schema specs
- development instructions in `AGENTS.md`

So the adaptation is:

- keep the spirit of explicit operational contracts
- do not force the entire system into one instruction file

### 4. Multi-User Scope Changes Everything

The original pattern works naturally for personal or small-team use.

StrataWiki must account for:

- shared scope
- tenant scope
- user scope
- ACL filtering
- stale and invalid states
- snapshot-aware explanation

This makes the system more like a knowledge platform than a personal notebook.

### 5. Search Is Important but Not Sufficient

The original pattern points out that markdown search becomes useful as the knowledge base grows.

This is still true, but in StrataWiki search has to be interpreted carefully.

Markdown search tools are useful for:

- docs
- dev-wiki
- rendered shared pages
- rendered personal pages

They are not enough for:

- canonical Fact storage
- dependency routing
- stale propagation
- ACL-safe system-state queries

## The Adapted StrataWiki Pattern

The adapted pattern looks like this.

### Layer 1: Raw Source Snapshots

Sources are fetched or collected and stored as versioned snapshots.

Examples:

- job posting payloads
- company hiring pages
- CSV extracts
- user-uploaded notes
- meeting notes
- API responses

These are not modified after ingestion; new versions appear as new snapshots.

### Layer 2: Fact Canonical Layer

Facts are normalized, deduplicated, and stored canonically.

This is where the system keeps:

- canonical entities
- observed attributes
- explicit relationships
- source provenance
- snapshot lineage

This is not a wiki. It is a structured base layer.

### Layer 3: Interpretation Canonical Layer

Interpretation stores shared derived meaning.

This is where the system maintains:

- trends
- comparisons
- contradiction candidates
- opportunity summaries
- risk summaries
- relation-rich derived knowledge

This layer is where the original wiki's synthesis behavior now lives canonically.

### Layer 4: Personal Layer

Personal stores user-scoped plans, notes, and personalized syntheses.

This includes:

- strategy pages
- user-specific explanations
- plans
- gap analyses
- cached answer artifacts

Personal outputs should always reference upstream snapshots and anchors.

### Layer 5: Rendered Wiki Views

Markdown still matters here.

Rendered pages exist for:

- shared interpretation browsing
- personal plan readability
- developer documentation and investigation support

This is where the original LLM Wiki browsing experience survives in adapted form.

## Adapted Operation Model

### Ingest

Original pattern:

- read source
- write summary page
- update linked pages

StrataWiki adaptation:

- fetch or receive source snapshot
- normalize source
- write Fact records
- publish Fact snapshot metadata
- mark affected Interpretation partitions stale
- schedule projection work
- optionally refresh rendered shared pages

### Query

Original pattern:

- search wiki
- read pages
- synthesize answer

StrataWiki adaptation:

- resolve user scope and profile version
- search Personal first
- expand into Interpretation
- drill into Fact evidence if needed
- synthesize answer
- optionally persist Personal output as a rendered artifact with anchors

### Lint

Original pattern:

- detect contradictions, orphan pages, missing cross-references, stale content

StrataWiki adaptation:

- detect stale rendered views
- detect invalid snapshot dependencies
- detect contradiction drift
- detect missing rendered pages for important interpretations
- detect dependency index gaps
- detect schema version mismatches
- detect ACL leakage risks in graph or retrieval paths

## How qmd and Similar Tools Fit

The original pattern mentions markdown search tools such as qmd.

In StrataWiki, tools like qmd are best understood as:

- auxiliary retrieval over readable markdown artifacts
- developer and analyst productivity tools
- possible search support for rendered shared pages and personal pages

They are not the canonical storage backbone.

This is the right adaptation:

- use qmd-like tooling where markdown browsing is the interface
- do not confuse markdown retrieval with canonical system state

## Development Adaptation

The original pattern is also useful at the repository development level.

StrataWiki now uses:

- `docs/` for official architecture and specifications
- `dev-wiki/` for working knowledge, experiments, and design traces

This is effectively the original LLM Wiki pattern applied to the development process itself.

That means the pattern now operates at two levels:

- product architecture level
- repository development workflow level

## What StrataWiki Should Explicitly Reject

To avoid confusion, StrataWiki should explicitly reject these interpretations of the original pattern.

### Rejected Idea 1: The rendered wiki is the only authoritative knowledge base

Not true in StrataWiki.

### Rejected Idea 2: The system can remain markdown-only while scaling to multi-user operation cleanly

Not true in StrataWiki.

### Rejected Idea 3: Search tooling can replace structured state management

Not true in StrataWiki.

### Rejected Idea 4: Domain-specific ingestion can be ignored in favor of a universal raw-document workflow

Not true in StrataWiki.

## Final Adaptation Summary

The original LLM Wiki pattern gives StrataWiki its philosophical foundation:

- knowledge should accumulate
- synthesis should persist
- good answers should become durable artifacts
- maintenance should be cheap because the LLM performs it

But StrataWiki changes the implementation model:

- structured canonical layers replace markdown-only truth
- rendered wiki pages remain important as readable artifacts
- graph, snapshots, caching, and invalidation become first-class concerns
- domain plugins replace one-size-fits-all ingestion semantics
- multi-user scope becomes a core systems concern

## One-Sentence Summary

StrataWiki adopts the LLM Wiki pattern as a compounding knowledge philosophy, but reimplements it as a multi-layer MCP system where markdown is a readable view, not the only source of truth.
