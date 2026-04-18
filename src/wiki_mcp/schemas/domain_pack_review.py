from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


ValidationIssueSeverity = Literal["error", "warning"]
DomainPackCompatibilityDecision = Literal["auto_pass", "manual_review", "auto_block"]


class DomainPackValidationIssue(TypedDict, total=False):
    code: str
    path: str
    message: str
    severity: ValidationIssueSeverity
    details: dict[str, Any]


class DomainPackValidationReport(TypedDict):
    ok: bool
    issues: list[DomainPackValidationIssue]
    errors: list[DomainPackValidationIssue]
    warnings: list[DomainPackValidationIssue]


class DomainPackCompatibilityIssue(TypedDict, total=False):
    code: str
    path: str
    message: str
    decision: DomainPackCompatibilityDecision
    breaking: bool
    review_required: bool
    migration_required: bool
    old_value: Any
    new_value: Any
    details: dict[str, Any]


class DomainPackCompatibilityReport(TypedDict):
    compatible: bool
    review_required: bool
    migration_required: bool
    recommended_action: DomainPackCompatibilityDecision
    active_pack_version: str
    candidate_pack_version: str
    issues: list[DomainPackCompatibilityIssue]
    breaking_changes: list[DomainPackCompatibilityIssue]
    review_required_issues: list[DomainPackCompatibilityIssue]


class DomainPackRegistrationError(TypedDict, total=False):
    code: str
    message: str
    details: dict[str, Any]


class DomainPackReviewAudit(TypedDict, total=False):
    reviewed_by: str
    reviewed_at: str
    decision_reason: str
    migration_plan_ref: str
    approved_for_activation: bool


class DomainPackApprovalReport(TypedDict, total=False):
    ok: bool
    domain: str
    candidate_pack_version: str
    active_pack_version: str
    validation: DomainPackValidationReport
    compatibility: DomainPackCompatibilityReport
    activation_safe: bool
    review_required: bool
    recommended_action: DomainPackCompatibilityDecision
    registered: bool
    activated: bool
    review_audit: DomainPackReviewAudit
    registration_error: DomainPackRegistrationError
