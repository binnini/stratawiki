from __future__ import annotations

from typing import Any, Literal, TypedDict


RecruitingPayloadProvider = Literal["worknet"]
RecruitingSourceKind = Literal["open_recruitment"]


class RecruitingSourceProvenance(TypedDict):
    """Provider-level provenance for an externally normalized recruiting source."""

    provider: RecruitingPayloadProvider
    kind: RecruitingSourceKind
    source_id: str
    company_source_id: str | None
    source_url: str | None
    mobile_source_url: str | None
    fetched_at: str
    content_hash: str | None


class RecruitingJobPostingPayload(TypedDict):
    """Normalized job posting body returned by an external recruiting provider."""

    title: str
    company_name: str
    company_type: str | None
    employment_type: str | None
    starts_at: str | None
    closes_at: str | None
    summary: str | None
    application_method: str | None
    required_documents: str | None
    acceptance_announcement: str | None
    inquiry: str | None
    notes: str | None


class RecruitingCompanyCoordinates(TypedDict):
    latitude: str | None
    longitude: str | None


class RecruitingCompanyPayload(TypedDict):
    """Normalized company body returned by an external recruiting provider."""

    source_company_id: str | None
    name: str
    company_type: str | None
    homepage_url: str | None
    business_number: str | None
    summary: str | None
    description: str | None
    main_business: str | None
    logo_url: str | None
    coordinates: RecruitingCompanyCoordinates | None


class RecruitingJobPayload(TypedDict):
    """Normalized job code/name pair attached to a recruiting source."""

    source_code: str | None
    name: str | None


class RecruitingSelectionStepPayload(TypedDict):
    """Normalized selection step attached to a recruiting source."""

    name: str | None
    schedule: str | None
    description: str | None
    note: str | None


class RecruitingRecruitmentSectionPayload(TypedDict):
    """Normalized recruitment section attached to a recruiting source."""

    title: str | None
    role_description: str | None
    selection_description: str | None
    location: str | None
    career_requirement: str | None
    education_requirement: str | None
    other_requirement: str | None
    openings: str | None
    note: str | None


class RecruitingAttachmentPayload(TypedDict):
    """Normalized attachment metadata attached to a recruiting source."""

    file_name: str


class RecruitingSourcePayload(TypedDict):
    """Controlled intermediate recruiting payload accepted by StrataWiki adapters."""

    payload_version: str
    source: RecruitingSourceProvenance
    posting: RecruitingJobPostingPayload
    company: RecruitingCompanyPayload | None
    jobs: list[RecruitingJobPayload]
    recruitment_sections: list[RecruitingRecruitmentSectionPayload]
    selection_steps: list[RecruitingSelectionStepPayload]
    attachments: list[RecruitingAttachmentPayload]
    raw: dict[str, Any] | None
