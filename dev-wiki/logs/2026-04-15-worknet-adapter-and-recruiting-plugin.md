# 2026-04-15 WorkNet Adapter And Recruiting Plugin

## Summary
Added the first concrete bridge from an external normalized recruiting provider into StrataWiki.
The implementation now has two connected layers:

1. `WorknetRecruitingExternalAdapter`
2. `RecruitingSourceIngestionPlugin`

This is the first end-to-end path from:
external recruiting payload -> `SourceRecord` -> thin recruiting fact decomposition.

## What Was Added
- `src/wiki_mcp/schemas/external_recruiting_payload.py`
  - Python-side schema for the external normalized recruiting payload.
- `src/wiki_mcp/adapters/sources/worknet.py`
  - WorkNet external adapter.
  - Converts external normalized payload into StrataWiki `SourceRecord`.
  - Renders a readable markdown body from the recruiting payload.
- `src/wiki_mcp/domains/recruiting/ingestion.py`
  - First recruiting domain ingestion plugin.
  - Extracts a minimal set of fact records and relations.

## Current Fact Decomposition
Current minimal fact types:
- `job_posting`
- `company`
- `job`
- `recruitment_section`

Current minimal relation types:
- `posted_by`
- `classified_as`
- `has_section`

This is intentionally incomplete.
It is only a first-pass decomposition used to validate the architecture boundary.

## Architectural Meaning
This work confirms the intended split:
- external integration package owns source acquisition and domain-normalized payloads
- StrataWiki external adapter owns payload-to-`SourceRecord` translation
- StrataWiki domain plugin owns `SourceRecord`-to-`FactRecord[]` decomposition
- StrataWiki core ingestion service will later own persistence, snapshots, outbox, and propagation

## Known Limitations
- recruiting schema is still provisional
- no unit tests yet for the plugin or adapter
- no `CoreIngestionService` implementation yet
- no repository implementation yet
- `selection_step`, `attachment`, `location`, `compensation`, and requirement facts are not yet split into dedicated records
- company matching remains upstream-provider dependent

## Next Recommended Step
Add tests that feed a WorkNet-style normalized recruiting payload into the adapter and plugin, then inspect the resulting `SourceRecord`, `FactRecord[]`, and `FactRelation[]`.
