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

## Note

This branch intentionally introduces the `dev-wiki/` concept and folder structure only.
It does not import old branch-specific working notes as official project direction.
