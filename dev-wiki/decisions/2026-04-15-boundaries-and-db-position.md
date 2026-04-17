# 2026-04-15 Boundaries And Database Position

## Decision
StrataWiki is positioned as a separate knowledge backend service.
PostgreSQL is a StrataWiki-owned external datastore.

## Why
The system owns Fact, Interpretation, Personal, snapshot, outbox, and dependency lifecycle.
This makes strong internal coupling to the datastore acceptable.
The real risk is schema leakage into WAS, MCP contracts, domain plugins, or external ingestion systems.

## Boundary Rule
- strong StrataWiki -> DB coupling is acceptable
- direct dependency from other systems to StrataWiki DB is not acceptable
