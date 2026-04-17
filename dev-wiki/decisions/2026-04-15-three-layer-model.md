# 2026-04-15 Three-Layer Model

## Decision
Adopt a three-layer knowledge model:
- Fact
- Interpretation
- Personal

## Why
A markdown-only wiki is not sufficient for multi-user operation, personalization, cache invalidation, snapshots, and dependency routing.
The system needs a separation between observed data, shared derived meaning, and user-scoped outputs.

## Implications
- Fact becomes the canonical observed layer.
- Interpretation becomes the shared derived layer.
- Personal becomes user-scoped readable and cached output.
- Rendered markdown is no longer the sole source of truth.
