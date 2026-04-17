# AGENTS.md

## Purpose

This file defines the default working agreement for agents contributing to this repository.

Agents should treat the documentation in `docs/` as the design source of truth and should use GitHub Issues as the default unit of planned implementation work.

## Source of Truth

Before starting implementation work, agents should consult the relevant specs in `docs/`.

Important starting points:

- `docs/implementation-roadmap.md`
- `docs/three-layer-data-model-spec.md`
- `docs/interpretation-schema-and-lifecycle-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`
- `docs/deployment-and-operations-spec.md`

If code and docs disagree, prefer the docs unless the user explicitly directs otherwise.

## Issue-Driven Workflow

Agents should use GitHub Issues as the default planning and tracking mechanism for non-trivial work.

Use this rule of thumb:

- small one-file fixes may proceed without creating a new issue
- any multi-step feature, refactor, architectural change, or cross-module task should be tied to a GitHub issue

Recommended workflow:

1. find an existing issue that matches the task
2. if no issue exists, prepare one before large implementation work
3. keep implementation scope aligned with the issue title and acceptance criteria
4. reference the issue in commits, PRs, and progress updates when practical

## Backlog and Roadmap

Agents should map work against:

- roadmap phases in `docs/implementation-roadmap.md`
- active GitHub Issues
- current sprint or milestone if one exists

When suggesting new work, agents should prefer creating or updating issues rather than tracking large plans only in chat.

## Working Against Issues

When implementing from an issue, agents should:

- restate the goal in concrete repository terms
- identify the relevant spec documents
- keep the change set scoped to the issue
- call out any mismatch between the issue and the current docs

If an issue is too large, agents should suggest splitting it into smaller issues before broad implementation.

## Daily and Progress Tracking

For multi-step work, agents should think in terms of:

- backlog
- in-progress work
- blockers
- done criteria

If the user is using a GitHub Project board, agents should align their updates to that workflow:

- `Backlog`
- `Ready`
- `In Progress`
- `Blocked`
- `Review`
- `Done`

## GitHub Projects and Labels

If the repository uses GitHub Issues and Projects, agents should prefer:

- using existing labels
- respecting milestone boundaries
- keeping issue titles implementation-oriented

Recommended examples already discussed in this repository include:

- `mvp`
- `week-2`
- `fact`
- `interpretation`
- `retrieval`
- `personal`
- `graph`
- `cache`
- `operator`
- `deployment`

## When to Update Docs

Agents should update docs when:

- implementation changes architectural assumptions
- lifecycle/status semantics change
- tool contracts change
- roadmap sequencing changes
- deployment/runtime constraints change

Do not let implementation drift far ahead of the specs in this repository.

## Preferred Implementation Order

When unsure, agents should prefer this priority order:

1. preserve canonical `Fact` integrity
2. preserve `Interpretation` lifecycle and evidence contracts
3. preserve retrieval and orchestration boundaries
4. preserve snapshot, cache, and stale semantics
5. preserve deployment and operator visibility constraints

## Pull Request and Commit Hygiene

When preparing a PR or branch:

- use focused branches
- keep commits scoped and descriptive
- mention the relevant issue number if available
- avoid bundling unrelated refactors into feature work

## Practical Constraint

If an agent cannot directly create GitHub Issues due to integration permissions, it should still:

- produce issue-ready titles and bodies
- ask the user to register them or provide a scriptable path
- continue to organize work as issue-sized units

The absence of direct write permission to GitHub Issues is not a reason to skip issue-oriented planning.
