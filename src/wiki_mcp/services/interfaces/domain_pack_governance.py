from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.domain_pack import DomainPack
from wiki_mcp.schemas.domain_pack_review import (
    DomainPackApprovalReport,
    DomainPackApprovalAuditRecord,
    DomainPackCompatibilityReport,
    DomainPackReviewAudit,
    DomainPackValidationReport,
)


class DomainPackValidator(Protocol):
    """Validate one domain pack artifact before registration."""

    def validate(
        self,
        pack: DomainPack,
    ) -> DomainPackValidationReport:
        """Return a structured report for one candidate pack."""


class DomainPackCompatibilityChecker(Protocol):
    """Compare one active pack against one candidate upgrade."""

    def compare(
        self,
        *,
        active_pack: DomainPack,
        candidate_pack: DomainPack,
    ) -> DomainPackCompatibilityReport:
        """Return a structured compatibility report between two pack versions."""


class DomainPackApprovalService(Protocol):
    """Review and optionally register domain packs through validator/checker gates."""

    def review_registration(
        self,
        candidate_pack: DomainPack,
        review_audit: DomainPackReviewAudit | None = None,
    ) -> DomainPackApprovalReport:
        """Return validation and compatibility results without mutating the registry."""

    def register_pack(
        self,
        candidate_pack: DomainPack,
        *,
        activate: bool = False,
        review_audit: DomainPackReviewAudit | None = None,
    ) -> DomainPackApprovalReport:
        """Validate, compare, and register a candidate pack when allowed."""


class DomainPackReviewAuditRepository(Protocol):
    """Durable storage boundary for approval-time governance audit records."""

    def append_record(
        self,
        record: DomainPackApprovalAuditRecord,
    ) -> str:
        """Persist one audit record and return its stored id."""
