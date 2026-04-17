# Docs Cleanup Checklist

## Purpose

This checklist captures the remaining documentation cleanup items before implementation backlog breakdown.

It is intentionally short and execution-oriented.

## Completed

- added LLM orchestration and retrieval strategy
- added interpretation schema and lifecycle spec
- added deployment and operations spec
- updated roadmap with retrieval, operator, and deployment workstreams

## Remaining High-Value Cleanup

### 1. Terminology Alignment

- keep `published` as the interpretation-specific active shared state
- keep `active` as the generic cross-layer record status where needed
- prefer `rendered page` for markdown artifacts
- prefer `curated retrieval` and `exploratory retrieval` for retrieval modes

### 2. Cross-Document References

- ensure data model links to interpretation lifecycle detail
- ensure roadmap points to the main spec for each phase
- ensure architecture remains the top-level map, not the place for deep detail

### 3. Tool and Lifecycle Parity

- keep proposal, validation, publish, and status inspection tools aligned with interpretation lifecycle states
- keep retrieval and exploration tools aligned with orchestration and graph specs

### 4. Implementation Entry Aids

- keep at least one compressed design summary for implementers
- make phase dependencies explicit in the roadmap

## Suggested Last Check Before Sprint Planning

- verify terminology consistency across all spec titles and status names
- verify every roadmap phase points to at least one detailed spec
- verify tool contracts exist for the highest-risk lifecycle transitions
- verify deployment constraints do not conflict with local-first development assumptions
