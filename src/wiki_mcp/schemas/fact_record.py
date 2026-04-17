from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class FactRecord(TypedDict):
    """Domain-neutral envelope for canonical Fact records."""

    id: str
    domain: str
    entity_type: str
    canonical_key: str
    attributes: dict[str, Any]
    scope: str
    fact_snapshot_id: NotRequired[str]
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]
    schema_version: str
    provenance: dict[str, Any]
