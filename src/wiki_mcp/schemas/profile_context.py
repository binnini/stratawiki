from __future__ import annotations

from typing import Any, TypedDict


class ProfileContext(TypedDict):
    """User or tenant context used to personalize retrieval and outputs."""

    user_id: str
    tenant_id: str
    domain: str
    profile_version: str
    goals: list[str]
    preferences: dict[str, Any]
    attributes: dict[str, Any]
