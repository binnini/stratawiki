# PostgreSQL Storage

This directory documents the StrataWiki-owned PostgreSQL storage baseline.

## Ownership

- PostgreSQL is an external infrastructure dependency.
- Schema and migration source ownership remain inside the StrataWiki repository.
- Alembic is the migration entrypoint.

## Logical Schemas

- `fact`: generic canonical fact envelopes and relations
- `interp`: canonical interpretation records
- `personal`: user-scoped metadata and profile context
- `ops`: snapshot publication state and outbox coordination
- `graph`: dependency reverse indexes and rendered page metadata

## Bootstrap

Default local bootstrap:

1. Run `scripts/bootstrap_db.sh`
2. Run `pytest -q`

`scripts/bootstrap_db.sh` will:

- start the local `postgres` Docker Compose service
- reuse the existing `stratawiki-postgres` container when another local
  worktree already created it
- wait until the database is reachable
- run `scripts/db_upgrade.sh`

`scripts/db_upgrade.sh` applies Alembic migrations against `DATABASE_URL` and
fails fast with a clear message if the target database is unreachable.

## Test Workflow

`tests/conftest.py` now tries to auto-bootstrap the default local database URL
when integration fixtures are requested and `DATABASE_URL` is unset.

That means the default local workflow is:

1. Run `pytest -q`

If you want to skip DB auto-bootstrap and keep the old skip-on-missing-DB
behavior, set `STRATAWIKI_PG_AUTO_BOOTSTRAP=0`.

If you want to target a different database:

1. Export `DATABASE_URL`
2. Run `scripts/db_upgrade.sh`
3. Run `pytest -q`

The initial migration creates all required logical schemas, tables, indexes, and constraints for the StrataWiki v1 storage baseline.
