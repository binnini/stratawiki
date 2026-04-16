# Personal Regeneration Slice

## Context

The repository already had:

- Fact ingestion
- Interpretation projection
- Personal stale marking
- outbox retry and backoff

That meant downstream invalidation existed, but stale Personal records still had to be refreshed manually.

## Current Question

What is the smallest Personal regeneration path that proves the intended ownership split without introducing LLM generation, retrieval ranking, or a richer rendering subsystem yet?

## Observations

- Personal records already store snapshot_ref, profile_version, summary, body_path, and provenance.
- personal.profile_context already stores enough information to build a deterministic profile-aware refresh.
- interpretation records now exist in a stable enough shape to feed a first deterministic Personal rewrite.
- filesystem rendering storage already exists and is good enough for the first readable Personal artifact rewrite.

## Options

- Stop at stale marking and leave regeneration entirely manual.
- Regenerate Personal metadata only and postpone markdown rewriting.
- Regenerate both Personal metadata and markdown from the stale event payload plus current profile and interpretation state.

## Decision or Working Direction

Take the third option.

The implemented flow is:

- interpretation refresh emits interpretation_snapshot_published
- stale worker marks dependent Personal records stale and emits personal_records_marked_stale
- regeneration worker claims personal_records_marked_stale
- regeneration service loads the affected Personal records
- regeneration service loads current profile_context for the user scope
- regeneration service loads the triggering shared interpretations
- Personal metadata is refreshed to the new fact plus interpretation plus profile snapshot tuple
- markdown is rewritten through the filesystem rendering repository
- the worker emits personal_records_regenerated

This gives the repository its first true refresh path for user-scoped artifacts rather than only invalidation.

## Open Questions

- Whether Personal regeneration should stay deterministic for one more slice or move behind an LLM generation boundary next.
- Whether body_path should remain stable across regenerations or become versioned.
- Whether graph.rendered_page should be updated as part of the same regeneration transaction in the next pass.
- Whether personal_records_regenerated should trigger active-user warming or read-model publication work.

## Next Actions

- Add a richer Personal generation interface that can support LLM-backed plan synthesis.
- Decide how regenerated markdown should be indexed and exposed through MCP read paths.
- Connect regenerated Personal artifacts to rendered-page metadata or retrieval indexes.
- Add Postgres-backed integration coverage for Personal regeneration when a reachable DB is available.


## Follow-Up

The next pass is now partially complete.

- regenerated Personal markdown now upserts the matching graph.rendered_page row
- rendered-page metadata now carries the refreshed snapshot tuple and title metadata
- this gives dependency impact lookup and future read APIs a stable page-level pointer after regeneration

### Updated Open Questions

- whether the rendering write and rendered-page upsert should become one explicit rendering subsystem contract instead of one repository convenience class
- whether graph.rendered_page should also be refreshed for shared interpretation rendering in the next slice
- whether regenerated Personal pages should be exposed first through a read API or through retrieval-oriented listing tools
