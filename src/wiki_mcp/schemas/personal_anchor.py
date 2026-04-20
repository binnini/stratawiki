from __future__ import annotations

from typing import Literal, TypedDict


class PersonalAnchor(TypedDict):
    """Explicit Personal dependency anchor to a shared record."""

    layer: Literal["interpretation", "fact"]
    id: str
