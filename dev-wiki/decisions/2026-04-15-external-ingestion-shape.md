# 2026-04-15 External Ingestion Shape

## Decision
External ingestion systems should integrate with StrataWiki through a controlled intermediate domain payload, not raw provider responses and not StrataWiki internal FactRecord shapes.

## Why
This preserves a clean anti-corruption boundary.
External systems can remain source/domain oriented while StrataWiki keeps canonicalization, snapshot publication, propagation, and storage authority.

## Applied Example
WorkNet now exposes a normalized recruiting payload.
StrataWiki consumes it through `WorknetRecruitingExternalAdapter`, which stops at `SourceRecord`.
The recruiting domain plugin then decomposes that `SourceRecord` into initial fact envelopes.
