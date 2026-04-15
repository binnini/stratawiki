from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class FactRelation(TypedDict):
    """Domain-neutral envelope for canonical Fact relations."""

    domain: str
    relation_type: str
    from_canonical_key: str
    to_canonical_key: str
    scope: str
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]
    schema_version: str
    provenance: dict[str, Any]
    attributes: NotRequired[dict[str, Any]]
