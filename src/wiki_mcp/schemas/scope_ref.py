from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


ScopeValue = Literal["shared", "tenant", "user"]


class ScopeRef(TypedDict):
    """Scope envelope used for shared, tenant, and user-scoped operations."""

    scope: ScopeValue
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]
