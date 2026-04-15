# Ingest Entrypoint Vertical Slice

## Context

The repository already had:

- source adapter to `SourceRecord`
- recruiting domain plugin
- core ingestion service
- Postgres repositories

What was still missing was an application-facing entrypoint that actually wires those pieces together.

## Current Question

What is the smallest real ingest entrypoint that proves the intended service boundary without prematurely committing to full MCP server bootstrap?

## Observations

- `server.py` is still only a placeholder, so the next useful step is a service-level entrypoint rather than a full MCP runtime bootstrap.
- The docs consistently place plugin selection, canonical write orchestration, snapshot publication, and outbox emission on the StrataWiki side.
- The current external adapter path is already stable enough to support a `SourceRecord`-based entrypoint.

## Options

- Wait for full MCP server bootstrap and wire ingestion there later.
- Add a reusable application service now that exposes ingestion as an explicit entrypoint.

## Decision or Working Direction

Add a reusable application-facing entrypoint now.

The implemented shape is:

- `DefaultIngestionEntrypoint.ingest_source(source)`
- `DefaultIngestionEntrypoint.ingest_worknet_source(provider, source_id, ...)`
- `build_default_ingestion_entrypoint(connection)`
- `connect_postgres(...)`

The entrypoint returns structured success/error envelopes instead of leaking selection and validation failures as raw exceptions.

## Open Questions

- Whether the future MCP tool layer should expose the same result envelope directly or translate it again.
- Whether more connector-specific entrypoints should exist or whether adapter-specific methods should remain thin wrappers only.
- Whether runtime dependencies for the default entrypoint should move from optional-dev to main dependencies as bootstrap becomes more concrete.

## Next Actions

- Decide how this entrypoint should be exposed from the future MCP tool layer.
- Add failure-path tests for source fetch exceptions and ambiguous plugin registration.
- Consider moving DB connection/bootstrap wiring into a dedicated application bootstrap module as server implementation begins.
