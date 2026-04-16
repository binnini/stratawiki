# Service Boundary and Database Positioning

## Purpose

This document defines how StrataWiki should be positioned relative to:

- a separate WAS or product backend
- its PostgreSQL datastore

## Positioning

StrataWiki should be positioned as:

- a knowledge backend service
- a multi-layer knowledge operating system
- an MCP-native backend with internal service interfaces

It should not be positioned as:

- just a database
- just an MCP wrapper
- just a markdown wiki

## Relationship to WAS

A separate WAS or product backend should own:

- user-facing product APIs
- session and auth entrypoints
- UI-specific orchestration
- billing and organization logic
- product-specific response shaping

For external integrations such as Jobs-Wiki, the WAS should also distinguish:

- a command-facing dependency used for mutation delegation
- a read-facing dependency used for normal user-visible queries

These should not be collapsed into one assumed endpoint at the contract level.

StrataWiki should own:

- Fact canonicalization
- Interpretation canonicalization and refresh
- Personal knowledge generation
- snapshot publication
- dependency routing
- retrieval orchestration
- rendered artifact generation

## External Contract Naming

When documenting an external WAS integration, prefer:

- `MCP command facade` for the mutation-facing boundary
- `read authority` for the read-facing boundary

`read authority` means the external read-serving dependency whose responses the WAS treats as authoritative for user-visible state.
This naming is useful because it does not assume:

- the same deployment surface for reads and commands
- direct database access from the WAS
- schema or migration ownership by the WAS

## Database Position

PostgreSQL should be deployed as a separate infrastructure dependency.

This means:

- StrataWiki owns the schema and migrations
- StrataWiki does not treat PostgreSQL as an in-process implementation detail
- PostgreSQL is not the responsibility of the WAS

## Why the Database Should Be Separate

Separating the database makes the system boundary clearer.

Benefits:

- clearer operational ownership
- independent backup and restore
- easier scaling of the StrataWiki service layer
- cleaner deployment model
- reduced temptation to let the WAS write directly into StrataWiki internals

## Ownership Rule

The key rule is:

StrataWiki owns the data model, but not the physical database process.

That means:

- schema ownership remains inside StrataWiki
- migration ownership remains inside StrataWiki
- canonical interpretation of stored data remains inside StrataWiki

## Current Implementation Note

This ownership boundary is now reflected in the repository itself.

Current repo-owned database assets include:

- Alembic migration setup
- initial PostgreSQL migration
- local bootstrap scripts
- local Docker Compose definition for PostgreSQL
- repository implementations aligned to the Postgres storage contracts

The database process can still be run outside the application repository in real environments.
The important boundary is that schema shape, migration history, and storage semantics remain owned by StrataWiki.

## Recommended Deployment Shape

- product WAS
- StrataWiki backend service
- StrataWiki-owned PostgreSQL
- optional later dependencies such as object storage or vector search

## Final Position

StrataWiki is a separate knowledge backend service with its own PostgreSQL datastore.
The WAS should consume StrataWiki, not absorb its core data lifecycle responsibilities.
