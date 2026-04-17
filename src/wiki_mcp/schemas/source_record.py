from __future__ import annotations

from typing import Any, TypedDict


class SourceRecord(TypedDict):
    """Common source envelope produced by connectors before domain extraction."""

    source_id: str
    connector: str
    domain: str
    title: str
    body_markdown: str
    metadata: dict[str, Any]
    fetched_at: str
    content_hash: str
    status: str
