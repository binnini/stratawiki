# Dev Wiki

## Purpose

`dev-wiki/` is the local working notebook for active development.

It is useful for:

- implementation logs
- experiment notes
- debugging trails
- temporary decision records
- prompt drafts

## Source of Truth Rule

`docs/` is the official source of truth for architecture, roadmap, contracts, and lifecycle semantics.

`dev-wiki/` should not replace `docs/`.

Use `dev-wiki/` for working state and promote only stable conclusions into `docs/` in cleaned-up form.

## Suggested Structure

- `dev-wiki/architecture/`
- `dev-wiki/decisions/`
- `dev-wiki/experiments/`
- `dev-wiki/prompts/`
- `dev-wiki/logs/`

## Current Working Notes

- `dev-wiki/logs/2026-04-17-issue-3-fact-storage-audit.md`
- `dev-wiki/logs/2026-04-17-issue-4-recruiting-fact-normalization.md`
- `dev-wiki/logs/2026-04-17-issue-5-interpretation-proposal-validation.md`
- `dev-wiki/logs/2026-04-17-phase-2-llm-gateway-handoff.md`
- `dev-wiki/logs/2026-04-18-issues-1-10-audit-and-manual-test-guide.md`
- `dev-wiki/decisions/2026-04-17-llm-gateway-operations-note.md`

## Note

This branch intentionally introduces the `dev-wiki/` concept and folder structure only.
It does not import old branch-specific working notes as official project direction.
