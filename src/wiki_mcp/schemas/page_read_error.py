from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class PageReadError(TypedDict):
    """Structured read-path error returned by page read entrypoints."""

    code: str
    message: str
    details: NotRequired[dict[str, Any]]
