from __future__ import annotations

from typing import Literal, TypedDict


class RetrievalProjectionRef(TypedDict):
    """Projection metadata for the current retrieval read slice."""

    family: Literal["retrieval"]
    scope: Literal["shared", "tenant", "user"]
    layers: list[str]
