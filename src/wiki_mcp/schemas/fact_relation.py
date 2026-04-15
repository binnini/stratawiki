from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class FactRelation(TypedDict):
    """Domain-neutral envelope for canonical Fact relations."""

    domain: str
    relation_type: str
    from_canonical_key: str
    to_canonical_key: str
    schema_version: str
    provenance: dict[str, Any]
    attributes: NotRequired[dict[str, Any]]
