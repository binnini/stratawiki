# StrataWiki-DB Decoupling Principles

## Purpose

This note clarifies how StrataWiki should relate to PostgreSQL.
The goal is not to make StrataWiki weakly coupled to its datastore at all costs.
The goal is to keep the **right kind of coupling** and avoid **schema leakage** into other layers.

## Core Position

StrataWiki is a data-model-driven knowledge backend.
It owns:

- Fact canonicalization
- Interpretation canonicalization
- Personal metadata
- snapshot publication
- outbox-based projection
- dependency impact lookup

Because of that, StrataWiki will naturally have a **strong internal dependency** on its PostgreSQL datastore.
This is acceptable.

The real risk is not strong ownership of the datastore.
The real risk is letting PostgreSQL table shapes leak into:

- WAS / application APIs
- MCP tool contracts
- domain plugin logic
- external ingestion systems
- rendering logic

## Acceptable Coupling

The following forms of coupling are expected and healthy:

- StrataWiki owns the PostgreSQL schema and migrations.
- StrataWiki repositories are implemented against StrataWiki-owned tables.
- Repository implementations understand table names, indexes, and persistence details.
- Schema evolution is driven by StrataWiki domain needs.
- PostgreSQL is treated as a StrataWiki-owned external datastore.

This is normal for a backend that owns its canonical data lifecycle.

## Dangerous Coupling

The following forms of coupling should be avoided:

- WAS reads or writes StrataWiki tables directly.
- MCP tools expose raw DB row shapes as external contracts.
- Domain plugins depend on SQL column names or SQL storage mechanics.
- External ingestion providers shape their payloads around StrataWiki DB tables.
- Rendered markdown and graph artifacts become the source of truth instead of canonical storage.
- Business logic is distributed across ad hoc SQL outside the repository layer.

This is not just strong coupling.
This is schema leakage.

## Boundary Rule

The correct boundary is:

- `StrataWiki -> DB`: strong ownership is acceptable
- `Other systems -> DB`: direct dependency is not acceptable

In other words:

- PostgreSQL is an internal persistence detail of StrataWiki
- repository contracts are the storage boundary
- service contracts and MCP tools are the external boundary

## Layering Rule

To keep the dependency healthy, StrataWiki should preserve these layers:

1. `MCP / internal service interface`
2. `service orchestration`
3. `repository interface`
4. `repository implementation`
5. `PostgreSQL schema`

Only the lower layers should know PostgreSQL details.
Upper layers should depend on repository or service contracts.

## Practical Rules

### 1. Repository interfaces are the main anti-leak boundary

- Services should call repositories.
- Services should not construct SQL.
- MCP tools should not know table names.
- Domain plugins should not know table names.

### 2. Table names are not public API

- `fact.record_envelopes`
- `interp.record`
- `personal.record`
- `ops.outbox_event`
- `graph.dependency_edge`

These are internal storage structures.
They are not part of the MCP contract.
They are not part of the WAS contract.

### 3. Envelope-first storage helps evolution

The current envelope-first design is useful because it keeps the DB aligned with StrataWiki without prematurely freezing domain-specific normalized schemas.

This means StrataWiki can later:

- add recruiting-specific normalized tables
- optimize interpretation storage
- split rendered metadata structures

without immediately breaking service boundaries.

### 4. External systems integrate through adapters, not tables

External ingestion systems should produce:

- source payloads
- normalized domain payloads

They should not write StrataWiki tables directly.

### 5. WAS consumes StrataWiki, not PostgreSQL

WAS should call:

- MCP tools
- internal service endpoints
- StrataWiki application contracts

WAS should not query StrataWiki's PostgreSQL tables directly.

## Heuristic

A useful heuristic is:

- If changing a table name requires changing repository code only, the coupling is healthy.
- If changing a table name requires changing WAS, MCP tools, or domain plugins, the coupling is unhealthy.

## Conclusion

StrataWiki is allowed to be strongly coupled to its PostgreSQL datastore because it owns the knowledge lifecycle.
That is not a design flaw.

What must be prevented is wider system dependence on StrataWiki's schema.
The rule is simple:

- strong `StrataWiki <-> DB` coupling is acceptable
- broad `system <-> StrataWiki DB` coupling is not

The design goal is therefore not database independence.
The design goal is **database containment**.
