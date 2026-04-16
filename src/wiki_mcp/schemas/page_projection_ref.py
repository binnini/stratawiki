from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


class PageProjectionRef(TypedDict):
    """Projection metadata for the current rendered-page read slice."""

    family: Literal["document"]
    layer: NotRequired[str]
    scope: Literal["shared", "tenant", "user"]
