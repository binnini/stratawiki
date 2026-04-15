from __future__ import annotations

from typing import Any, TypedDict


class FactRecord(TypedDict):
    """Domain-neutral envelope for canonical Fact records."""

    id: str
    domain: str
    entity_type: str
    canonical_key: str
    attributes: dict[str, Any]
    scope: str
    schema_version: str
    provenance: dict[str, Any]
