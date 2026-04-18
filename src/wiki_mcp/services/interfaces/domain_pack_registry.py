from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.domain_pack import DomainPack


class DomainPackRegistry(Protocol):
    """Registry contract for versioned Domain Pack artifacts."""

    def register(self, pack: DomainPack, *, activate: bool = False) -> None:
        """Register one domain pack artifact with an optional activation step."""

    def get(self, domain: str, pack_version: str | None = None) -> DomainPack:
        """Resolve one registered pack by domain and optionally by explicit version."""

    def has(self, domain: str, pack_version: str | None = None) -> bool:
        """Return whether a pack can be resolved for the provided identity."""

    def list_versions(self, domain: str) -> list[str]:
        """Return registered versions for one domain in registration order."""

    def get_active_version(self, domain: str) -> str | None:
        """Return the currently active version for a domain, if one exists."""

    def set_active_version(self, domain: str, pack_version: str) -> None:
        """Point default resolution for a domain at a registered pack version."""
