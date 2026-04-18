from __future__ import annotations

from collections.abc import Iterable

from wiki_mcp.schemas.domain_pack import DomainPack


class DomainPackRegistryError(RuntimeError):
    """Base error for domain pack registration and lookup failures."""

    code = "domain_pack_registry_error"

    def __init__(
        self,
        message: str,
        *,
        domain: str,
        pack_version: str | None = None,
        available_versions: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.domain = domain
        self.pack_version = pack_version
        self.available_versions = list(available_versions or [])


class DomainPackNotRegisteredError(DomainPackRegistryError):
    code = "domain_pack_not_registered"

    def __init__(self, domain: str) -> None:
        super().__init__(
            f"No domain pack is registered for domain {domain!r}.",
            domain=domain,
        )


class UnsupportedDomainPackVersionError(DomainPackRegistryError):
    code = "unsupported_domain_pack_version"

    def __init__(self, domain: str, pack_version: str, available_versions: list[str]) -> None:
        versions_text = ", ".join(repr(version) for version in available_versions) or "none"
        super().__init__(
            (
                f"Domain pack {domain!r} does not support version {pack_version!r}. "
                f"Available versions: {versions_text}."
            ),
            domain=domain,
            pack_version=pack_version,
            available_versions=available_versions,
        )


class DomainPackVersionAlreadyRegisteredError(DomainPackRegistryError):
    code = "domain_pack_version_already_registered"

    def __init__(self, domain: str, pack_version: str) -> None:
        super().__init__(
            f"Domain pack {domain!r} version {pack_version!r} is already registered.",
            domain=domain,
            pack_version=pack_version,
        )


class DomainPackApprovalRequiredError(DomainPackRegistryError):
    code = "domain_pack_approval_required"

    def __init__(self, domain: str, *, action: str) -> None:
        super().__init__(
            (
                f"Direct registry {action} for domain pack {domain!r} is not allowed. "
                "Use the DomainPackApprovalService instead."
            ),
            domain=domain,
        )


def _pack_identity(pack: DomainPack) -> tuple[str, str]:
    manifest = pack.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError("DomainPack must include a manifest mapping.")

    domain = str(manifest.get("domain") or "").strip()
    pack_version = str(manifest.get("pack_version") or "").strip()
    if not domain:
        raise ValueError("DomainPack manifest.domain must be a non-empty string.")
    if not pack_version:
        raise ValueError("DomainPack manifest.pack_version must be a non-empty string.")
    return domain, pack_version


class InMemoryDomainPackRegistry:
    """Default in-memory registry for versioned Domain Pack artifacts."""

    def __init__(self, packs: Iterable[DomainPack] | None = None) -> None:
        self._packs_by_domain: dict[str, dict[str, DomainPack]] = {}
        self._active_versions: dict[str, str] = {}

        for pack in packs or []:
            self.register_approved(pack)

    def register(self, pack: DomainPack, *, activate: bool = False) -> None:
        domain, _ = _pack_identity(pack)
        raise DomainPackApprovalRequiredError(domain, action="registration")

    def register_approved(self, pack: DomainPack, *, activate: bool = False) -> None:
        domain, pack_version = _pack_identity(pack)
        versions = self._packs_by_domain.setdefault(domain, {})
        if pack_version in versions:
            raise DomainPackVersionAlreadyRegisteredError(domain, pack_version)

        versions[pack_version] = pack
        if activate:
            self._active_versions[domain] = pack_version

    def get(self, domain: str, pack_version: str | None = None) -> DomainPack:
        versions = self._packs_by_domain.get(domain)
        if versions is None:
            raise DomainPackNotRegisteredError(domain)

        resolved_version = pack_version or self._active_versions.get(domain)
        if resolved_version is None or resolved_version not in versions:
            raise UnsupportedDomainPackVersionError(
                domain,
                pack_version or "",
                list(versions),
            )
        return versions[resolved_version]

    def has(self, domain: str, pack_version: str | None = None) -> bool:
        try:
            self.get(domain, pack_version)
        except DomainPackRegistryError:
            return False
        return True

    def list_versions(self, domain: str) -> list[str]:
        versions = self._packs_by_domain.get(domain)
        if versions is None:
            return []
        return list(versions)

    def get_active_version(self, domain: str) -> str | None:
        return self._active_versions.get(domain)

    def set_active_version(self, domain: str, pack_version: str) -> None:
        raise DomainPackApprovalRequiredError(domain, action="activation")

    def set_active_version_approved(self, domain: str, pack_version: str) -> None:
        versions = self._packs_by_domain.get(domain)
        if versions is None:
            raise DomainPackNotRegisteredError(domain)
        if pack_version not in versions:
            raise UnsupportedDomainPackVersionError(domain, pack_version, list(versions))
        self._active_versions[domain] = pack_version
