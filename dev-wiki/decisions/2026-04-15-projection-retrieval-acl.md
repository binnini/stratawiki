# 2026-04-15 Projection Retrieval ACL

## Decision
Use the following v1 operational baseline:
- projection: outbox + worker
- retrieval: structured filtering + lexical search
- ACL: application-level scope enforcement

## Why
This is the simplest stack that still matches the multi-user knowledge backend model.
It avoids premature dependence on Kafka, vector infrastructure, graph databases, or DB-level RLS.

## Scope Model
Allowed scopes:
- shared
- tenant
- user
