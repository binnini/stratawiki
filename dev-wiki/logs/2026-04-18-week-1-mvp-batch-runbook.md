# Week 1 MVP Batch Runbook

## Purpose

This note defines how to process the remaining open `Week 1 MVP` issues in one long-running Codex session without stopping for manual approval between issues.

`docs/` remains the source of truth for architecture and contracts.
This file is only an execution runbook for the batch branch.

## Branch

- working branch: `batch/week-1-open-issues`
- base branch at creation time: `mvp/week-1`
- docs-alignment issue `#36` is already merged into the base branch before this runbook starts

## Goal

Process the remaining `Week 1 MVP` open issues in a stable order on one branch.

For each issue:

1. review the issue and relevant docs
2. implement the scoped change
3. run targeted tests
4. commit the change
5. push the branch
6. create a follow-up issue if needed
7. close the completed issue with the commit SHA

## Batch Order

### Backlog Hygiene First

Handle these before normal implementation work:

1. `#20` verify whether it is a duplicate of `#21`; if yes, close it as duplicate
2. `#28` verify whether it is a duplicate of `#29`; if yes, close it as duplicate
3. `#19` verify whether its remaining scope is distinct from closed issues `#5` and `#6`; if not, close or rewrite scope before continuing

### Implementation Order

Process in this order unless a docs-backed dependency requires a swap:

1. `#21` Harden canonical Fact identity and align Fact storage metadata with current docs
2. `#27` Persist explicit Personal anchors for curated retrieval
3. `#29` Index persisted personal anchors for retrieval reuse
4. `#23` Surface interpretation snapshot metadata in interpretation reads
5. `#25` Render shared pages from published interpretation records
6. `#24` Tighten duplicate publish policy for interpretation family partitions
7. `#26` Emit interpretation snapshot publication outbox event
8. `#22` Improve recruiting skill normalization with multilingual extraction

`#22` can move earlier only if the batch owner decides to split out the recruiting Fact workstream on purpose.

## Scope Rules

- Use GitHub Issues as the unit of work
- Keep each change set scoped to the current issue
- If code and docs disagree, prefer docs unless the issue clearly updates the design
- Do not silently widen an issue into adjacent architecture work
- If a task is clearly larger than one issue, create a follow-up issue before closing the current one

## Commit Rules

- Make at least one commit per completed issue
- Prefer one focused commit per issue unless a second cleanup commit is justified
- Mention the issue number in the commit message when practical

Recommended commit shape:

- `Resolve #21 Fact identity hardening`
- `Resolve #27 Persist Personal anchors`
- `Resolve #29 Reuse persisted Personal anchors in retrieval`

## Push and Close Rules

After each completed issue:

1. push `batch/week-1-open-issues` to `origin`
2. if a follow-up is needed, create it before closing the current issue
3. close the current issue with a comment that names the commit SHA and branch

Recommended close comment:

`Closed by <sha> on batch/week-1-open-issues.`

## Follow-Up Issue Rules

When creating a follow-up issue:

- use existing labels only
- apply `Week 1 MVP` milestone only if the remaining work is still genuinely in the Week 1 MVP scope
- keep titles implementation-oriented
- link back to the parent issue in the body

Typical labels to reuse:

- `mvp`
- `fact`
- `interpretation`
- `retrieval`
- `personal`
- `operator`
- `recruiting`
- `tools`
- `schemas`

## Duplicate Handling

If an issue is a duplicate:

1. confirm the active surviving issue
2. leave a short comment pointing to the surviving issue
3. close with duplicate reason if the tooling supports it, otherwise close with comment

## Test Rules

- Run targeted tests for the issue scope before closing
- Run broader regression tests when a change touches shared schemas, repositories, or bootstrap wiring
- If a test cannot run, say so in the closing comment and explain why

## tmux Codex Prompt

Use this as the initial Codex CLI task prompt inside tmux:

```text
Continue work on branch `batch/week-1-open-issues`.

Process open `Week 1 MVP` issues in this order:
1. backlog hygiene: #20, #28, #19
2. implementation: #21 -> #27 -> #29 -> #23 -> #25 -> #24 -> #26 -> #22

Rules:
- consult the relevant docs before each issue
- keep scope aligned to the current issue
- run targeted tests
- commit after each completed issue
- push after each commit
- create follow-up issues when needed using existing labels and milestone rules
- close completed issues with the commit SHA
- do not stop for approval between issues if the runtime policy already allows the needed git, gh, and test commands
- leave concise progress updates only at issue boundaries
```

## Stop Conditions

Stop the batch only if:

- a required command is blocked by permissions that cannot be auto-approved
- the repo enters a conflicting dirty state that was not created by the batch
- the docs and issue scope conflict in a way that requires a human product decision
- an unresolved production-risk bug is discovered outside the current issue scope

Otherwise continue until the ordered issue list is exhausted.
