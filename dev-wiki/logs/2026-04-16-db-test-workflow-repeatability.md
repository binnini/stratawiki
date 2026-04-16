# DB Test Workflow Repeatability

## Context

The repository already proved that local PostgreSQL plus Alembic plus pytest
integration works against a real database.

The remaining friction was operational:

- integration fixtures skipped easily when `DATABASE_URL` was unset or the local
  container was not already running
- bootstrap and migration steps were documented as separate manual commands
- the default local path was real, but not the easiest path

This task is limited to DB workflow ownership files and should avoid service
implementation files owned by other agents.

## Current Question

How can the repository make local DB-backed pytest runs reproducible by default
without changing the meaning of the integration tests?

## Observations

- `scripts/bootstrap_db.sh` previously started Docker Compose and immediately
  ran Alembic, which could race with PostgreSQL startup.
- the local Docker Compose file pins `container_name = stratawiki-postgres`, so
  parallel local worktrees can collide unless bootstrap reuses the existing
  container.
- `scripts/db_upgrade.sh` assumed the target database was already reachable and
  failed without a targeted hint.
- `tests/conftest.py` only attempted a direct connection and then skipped the
  integration fixtures, so a normal `pytest -q` on a fresh local machine could
  silently miss DB coverage.
- On this branch, some requested dev-wiki files from the handoff prompt were
  absent, so this note records the workflow decision locally in the current
  branch state.

## Options

- Keep the skip-first fixture behavior and only improve documentation.
- Auto-bootstrap the default local Postgres path in pytest, while preserving the
  ability to skip or target a custom database explicitly.

## Decision or Working Direction

Take the second option.

The workflow now aims to make the default local path executable:

- `scripts/bootstrap_db.sh` starts Docker Compose Postgres, waits for a real
  connection, and then delegates migration application to `scripts/db_upgrade.sh`
- `scripts/db_upgrade.sh` validates reachability first and emits a clear
  recovery hint when the database is not ready
- `tests/conftest.py` auto-bootstraps only the default local database path when
  `DATABASE_URL` is unset and `STRATAWIKI_PG_AUTO_BOOTSTRAP` is not disabled
- custom `DATABASE_URL` values still require an explicitly reachable database,
  which avoids hiding misconfiguration on non-default environments

## Open Questions

- Whether the repository should later add a dedicated `pytest` marker or command
  alias that isolates only the DB-backed integration subset.
- Whether CI should use the same bootstrap script directly so local and CI DB
  setup stay identical.
- Whether branch-local dev-wiki files that were referenced in the handoff prompt
  should be restored or promoted in a follow-up branch.

## Next Actions

- Run the bootstrap script against local Docker-backed Postgres.
- Run `pytest -q` in the dedicated worktree and record the result in the task
  summary.
- Commit only the DB workflow files and this log note.
- Keep shared-worktree cleanup limited to files that were unquestionably changed
  during this task to avoid cross-agent conflicts.
