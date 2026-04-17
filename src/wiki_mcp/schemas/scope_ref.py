from __future__ import annotations

from typing import NotRequired, TypedDict


class ScopeRef(TypedDict):
    """Scope envelope used for shared, tenant, and user-scoped operations."""

    scope: str
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]
