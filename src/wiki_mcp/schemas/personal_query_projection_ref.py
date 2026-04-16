from __future__ import annotations

from typing import Literal, TypedDict


class PersonalQueryProjectionRef(TypedDict):
    """Projection metadata for the current personal answer read slice."""

    family: Literal["answer"]
    kind: Literal["personal_query"]
    scope: Literal["shared", "tenant", "user"]
    layers: list[str]
