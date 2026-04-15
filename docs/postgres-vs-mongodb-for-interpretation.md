# PostgreSQL JSONB vs MongoDB for Interpretation Layer

## Purpose

This document compares two main candidates for the `Interpretation canonical` layer in StrataWiki:

- PostgreSQL with JSONB
- MongoDB

The question is not which database is better in the abstract.

The real question is:

Which storage choice gives StrataWiki the best trade-off between flexibility, operational simplicity, and future evolution for the Interpretation layer?

## Scope

This comparison applies to the `Interpretation canonical` layer only.

It does not directly apply to:

- `Fact`, which has different requirements and remains better aligned with structured relational storage
- `Personal`, which is user-scoped and partly rendered as markdown or view artifacts

## What Interpretation Needs

Interpretation records in StrataWiki are expected to be:

- shared rather than user-specific
- derived from Facts
- versioned and refreshable
- evidence-linked
- relation-rich
- subject-oriented
- domain-variable in shape
- rendered into markdown views when useful

Interpretation records are also likely to evolve faster than Fact schemas.

Typical fields include:

- subject and subject type
- claim and summary
- confidence
- evidence references
- freshness
- status
- render hints
- provenance
- relation edges to other interpretations
- schema version

This is an awkward fit for strict relational normalization, but also not a completely free-form document problem.

## Option 1: PostgreSQL JSONB

### Why it is attractive

PostgreSQL JSONB allows document-like records while keeping Interpretation close to the rest of the system.

This means:

- fewer infrastructure pieces
- simpler local development
- easier joins to Fact metadata and profile state
- easier transactional coordination for snapshot metadata
- easier operational consistency in version one

### Strengths

- operational simplicity
- one primary database for Fact, profile metadata, and interpretation metadata
- strong indexing options for both structured columns and JSONB fields
- easier implementation of outbox and projection workflows
- easier snapshot publishing when the source of truth is colocated
- easier backup and restore story early on
- easier access control integration if application and DB boundaries stay simple

### Weaknesses

- document mutation ergonomics are weaker than MongoDB
- some nested update patterns are awkward
- interpretation schemas that diverge significantly by domain can become messy
- JSONB queries can become harder to maintain than clean document queries
- if interpretation relations become very graph-like, the data model may feel strained

### Best Case for PostgreSQL JSONB

PostgreSQL JSONB is the better choice when:

- version one should minimize operational complexity
- the team already knows PostgreSQL well
- schema evolution is expected but not chaotic
- the first domain is narrow enough to validate interpretation patterns before scaling out
- cross-store consistency cost is considered more dangerous than document-shape inconvenience

## Option 2: MongoDB

### Why it is attractive

MongoDB fits the Interpretation layer naturally because Interpretation records are document-like and likely to vary by domain, family, and evolution stage.

This means:

- better document flexibility
- easier partial updates
- cleaner storage of evolving nested shapes
- better ergonomics for evidence arrays, relation arrays, and render hints

### Strengths

- excellent fit for document-oriented interpretation records
- easier partial mutation of nested fields
- more natural storage for heterogeneous interpretation shapes across domains
- easier evolution of record structure without relational awkwardness
- less pressure to prematurely normalize fields that may change later

### Weaknesses

- one more operational system to run
- Fact and Interpretation become cross-store by default
- projection and invalidation complexity increases sooner
- snapshot publication becomes more distributed
- debugging stale state across stores is harder
- ACL and audit pathways get more complex
- local development and deployment story become heavier

### Best Case for MongoDB

MongoDB is the better choice when:

- interpretation record structures are expected to change rapidly
- domain plugins are expected to diverge heavily in interpretation shape
- partial updates on nested documents are frequent and important
- the team is comfortable with multi-store systems early
- operational complexity is acceptable in exchange for better document ergonomics

## The Real Trade-Off

The deepest trade-off is not relational versus document.

It is:

- simpler system coordination now
n- versus better document fit now

Or more concretely:

- PostgreSQL JSONB optimizes for operational coherence
- MongoDB optimizes for interpretation-document ergonomics

For StrataWiki version one, the cost center is likely to be:

- cross-store consistency
- invalidation routing
- snapshot traceability
- explainability of stale versus fresh outputs

This is why PostgreSQL JSONB remains attractive even if MongoDB looks more elegant for Interpretation in isolation.

## Recruiting Domain Test

The recruiting domain is useful as the first stress test.

Interpretation examples include:

- market trend by region and seniority
- skill gap pattern for role transitions
- regional opportunity summary
- compensation interpretation
- company hiring pattern

These records are document-shaped, but still fairly structured.

They are not yet so unstructured that PostgreSQL JSONB clearly fails.

That means recruiting is a good domain for validating whether JSONB is sufficient before introducing MongoDB.

## Decision Matrix

### PostgreSQL JSONB

Pros:

- fewer systems to operate
- simpler snapshots and projection flows
- easier initial integration with Fact and profile metadata
- lower complexity for first implementation slice

Cons:

- interpretation documents may become awkward over time
- schema churn may make queries and updates less pleasant

### MongoDB

Pros:

- better native fit for interpretation documents
- easier nested and partial updates
- better long-term fit if interpretation becomes highly heterogeneous

Cons:

- more operational systems
- harder consistency boundaries
- more complicated debugging and invalidation paths

## Current Recommendation

For StrataWiki version one:

- prefer `PostgreSQL JSONB` for the Interpretation canonical layer
- design the `InterpretationRecord` interface as if it could later move to MongoDB
- keep storage access behind a clear repository or adapter boundary

This gives the project:

- simpler early implementation
- fewer infrastructure dependencies
- a better chance of validating the retrieval and invalidation model before optimizing document storage ergonomics

## Migration Trigger for MongoDB

Revisit the choice if one or more of these become true:

- interpretation schemas diverge strongly across domains
- partial document updates become common and painful
- JSONB query logic becomes harder to maintain than the surrounding system justifies
- rendering, retrieval, and versioning pressure make document ergonomics the primary bottleneck
- the team is ready to absorb multi-store operational complexity

## Suggested Implementation Rule

Code the Interpretation layer so that the rest of the system depends on:

- the `InterpretationRecord` contract
- repository interfaces
- snapshot and provenance contracts

and not directly on PostgreSQL-specific query assumptions.

This keeps the project open to MongoDB later without forcing MongoDB now.

## Final Position

MongoDB may ultimately be the more natural long-term home for Interpretation.

But for the first implementation of StrataWiki, PostgreSQL JSONB is the safer choice because it reduces system complexity at the exact stage where coordination, invalidation, and snapshot correctness matter most.
