from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.profile_context import ProfileContext


class ProfileContextService(Protocol):
    """Profile and context boundary for personalization."""

    def get_profile_context(
        self,
        domain: str,
        tenant_id: str,
        user_id: str,
    ) -> ProfileContext:
        """Return the current profile context used for personalized retrieval and generation."""
