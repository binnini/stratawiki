# StrataWiki Development Instructions

This repository uses a local development wiki to help the coding agent preserve context, compare design options, and accumulate implementation knowledge during development.

## Purpose

Use `dev-wiki/` aggressively during development as a working knowledge layer.

The goals are:
- preserve architectural reasoning across sessions
- avoid re-deriving the same design decisions repeatedly
- keep temporary notes out of official `docs/`
- promote only stable, reusable content into `docs/`

`docs/` is the official project documentation.
`dev-wiki/` is the working notebook.

## What the Agent Should Do

When working on substantial tasks, the agent should:

1. Read relevant official docs in `docs/` first
2. Read relevant working notes in `dev-wiki/` if they exist
3. Add short working notes to `dev-wiki/` during analysis or implementation when useful
4. Summarize stable conclusions back into `docs/` only when they are mature enough to be shared

The agent should treat `dev-wiki/` as internal working memory for the repository.

## When to Write to dev-wiki

Write or update `dev-wiki/` when:
- evaluating architecture alternatives
- comparing storage or indexing options
- tracing bugs across multiple files or layers
- recording implementation decisions before they are formalized
- collecting prompt experiments, retrieval experiments, or schema experiments
- tracking open questions, assumptions, and risks
- planning multi-step implementation work

Do not write to `dev-wiki/` for trivial one-file edits unless the reasoning is likely to matter later.

## dev-wiki Structure

Use these folders consistently:

- `dev-wiki/architecture/`
  Working architecture notes, diagrams in markdown, subsystem comparisons
- `dev-wiki/decisions/`
  Temporary decision logs before promotion to `docs/`
- `dev-wiki/experiments/`
  Prompt tests, retrieval tests, schema tests, ranking tests, performance notes
- `dev-wiki/prompts/`
  Reusable prompt drafts, evaluation prompts, extraction prompts
- `dev-wiki/logs/`
  Session logs, implementation checkpoints, debugging trails

## File Naming Guidance

Prefer date-prefixed kebab-case names for working notes.

Examples:
- `dev-wiki/logs/2026-04-15-schema-questions.md`
- `dev-wiki/experiments/2026-04-15-retrieval-ranking.md`
- `dev-wiki/decisions/2026-04-15-fact-store-options.md`

## Working Note Template

Use this template when creating a new development note:

```md
# Title

## Context

## Current Question

## Observations

## Options

## Decision or Working Direction

## Open Questions

## Next Actions
```

## Promotion Rule

If content in `dev-wiki/` becomes stable, reusable, and important for collaborators, promote it into `docs/` in cleaned-up form.

Promotion criteria:
- the idea survived at least one implementation pass or review
- the terminology is stable
- the decision is expected to matter later
- the content is useful to someone other than the original author

Do not simply move working notes verbatim into `docs/`.
Rewrite them into cleaner project documentation.

## Relationship to Official Docs

The current official design set lives in `docs/` and is the primary source of truth for architecture.

Important files include:
- `docs/mcp-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/three-layer-llm-wiki-mcp-idea.md`
- `docs/three-layer-data-model-spec.md`
- `docs/cache-invalidation-consistency-spec.md`
- `docs/graph-index-and-propagation-spec.md`
- `docs/mcp-tool-contract-spec.md`
- `docs/recruiting-domain-schema-spec.md`

Use `dev-wiki/` to extend these documents during active work, not to silently replace them.

## Specific Guidance for StrataWiki

During development, the agent should pay special attention to recording:
- Fact vs Interpretation vs Personal boundary decisions
- graph and dependency-index behavior
- cache invalidation assumptions
- ACL and scope edge cases
- domain plugin boundaries
- schema versioning concerns
- retrieval pipeline tradeoffs
- prompt patterns used for extraction, interpretation, and personalization

## What Is Not Needed

Do not restore the old markdown-only LLM Wiki repository structure unless there is a very specific reason.

The previous project may still be useful as historical inspiration for:
- page format ideas
- ingest workflow wording
- query workflow patterns
- graph UX inspiration

But StrataWiki does not need that old repository structure to use `dev-wiki/` effectively.

If historical material is needed later, bring back only small selected snippets or ideas, not the entire old project.
