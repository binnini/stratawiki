from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class IngestionError(TypedDict):
    """Structured ingestion error returned by application-facing entrypoints."""

    code: str
    message: str
    details: NotRequired[dict[str, Any]]
