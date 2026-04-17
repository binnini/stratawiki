# 2026-04-15 Storage Baseline

## Decision
Use the following v1 storage baseline:
- Fact: PostgreSQL
- Interpretation canonical: PostgreSQL JSONB
- Personal metadata: PostgreSQL
- Personal rendered body: filesystem markdown

## Why
This keeps infrastructure count low while preserving a future path toward document-oriented interpretation storage.
It also keeps snapshots, invalidation, and joins simpler in v1.

## Deferred
- MongoDB for interpretation canonical
- object storage for rendered artifacts
- vector DB
- graph DB
