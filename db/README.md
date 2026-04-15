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

1. Start Postgres with `docker compose up -d postgres`
2. Export `DATABASE_URL`
3. Run `python3 -m alembic upgrade head`

The initial migration creates all required logical schemas, tables, indexes, and constraints for the StrataWiki v1 storage baseline.
