from __future__ import annotations

from typing import Any, Protocol

from wiki_mcp.schemas.external_recruiting_payload import (
    RecruitingAttachmentPayload,
    RecruitingCompanyPayload,
    RecruitingJobPayload,
    RecruitingJobPostingPayload,
    RecruitingRecruitmentSectionPayload,
    RecruitingSelectionStepPayload,
    RecruitingSourcePayload,
)
from wiki_mcp.schemas.source_record import SourceRecord


class WorknetRecruitingSourceProvider(Protocol):
    """External normalized recruiting provider exposed by the WorkNet integration."""

    def get_recruiting_source(self, params: dict[str, Any]) -> RecruitingSourcePayload:
        """Return a controlled intermediate recruiting payload for one source id."""


def _add_line(lines: list[str], heading: str, value: str | None) -> None:
    if value:
        lines.append(f"- {heading}: {value}")


def _render_posting_block(posting: RecruitingJobPostingPayload) -> list[str]:
    lines = ["## Posting"]
    _add_line(lines, "Title", posting["title"])
    _add_line(lines, "Company", posting["company_name"])
    _add_line(lines, "Company Type", posting["company_type"])
    _add_line(lines, "Employment Type", posting["employment_type"])
    _add_line(lines, "Opens", posting["starts_at"])
    _add_line(lines, "Closes", posting["closes_at"])
    _add_line(lines, "Summary", posting["summary"])
    _add_line(lines, "Application Method", posting["application_method"])
    _add_line(lines, "Required Documents", posting["required_documents"])
    _add_line(lines, "Announcement", posting["acceptance_announcement"])
    _add_line(lines, "Inquiry", posting["inquiry"])
    _add_line(lines, "Notes", posting["notes"])
    return lines


def _render_company_block(company: RecruitingCompanyPayload | None) -> list[str]:
    if not company:
        return []

    lines = ["## Company"]
    _add_line(lines, "Name", company["name"])
    _add_line(lines, "Source Company ID", company["source_company_id"])
    _add_line(lines, "Company Type", company["company_type"])
    _add_line(lines, "Homepage", company["homepage_url"])
    _add_line(lines, "Business Number", company["business_number"])
    _add_line(lines, "Summary", company["summary"])
    _add_line(lines, "Description", company["description"])
    _add_line(lines, "Main Business", company["main_business"])
    _add_line(lines, "Logo URL", company["logo_url"])

    coordinates = company.get("coordinates")
    if coordinates and (coordinates.get("latitude") or coordinates.get("longitude")):
        _add_line(
            lines,
            "Coordinates",
            f"{coordinates.get('latitude')}, {coordinates.get('longitude')}",
        )

    return lines


def _render_jobs_block(jobs: list[RecruitingJobPayload]) -> list[str]:
    if not jobs:
        return []

    lines = ["## Jobs"]
    for job in jobs:
        label = job.get("name") or "Unknown"
        code = job.get("source_code")
        lines.append(f"- {label}" + (f" ({code})" if code else ""))
    return lines


def _render_sections_block(
    sections: list[RecruitingRecruitmentSectionPayload],
) -> list[str]:
    if not sections:
        return []

    lines = ["## Recruitment Sections"]
    for index, section in enumerate(sections, start=1):
        title = section.get("title") or f"Section {index}"
        lines.append(f"### {title}")
        _add_line(lines, "Role Description", section.get("role_description"))
        _add_line(lines, "Selection Description", section.get("selection_description"))
        _add_line(lines, "Location", section.get("location"))
        _add_line(lines, "Career Requirement", section.get("career_requirement"))
        _add_line(lines, "Education Requirement", section.get("education_requirement"))
        _add_line(lines, "Other Requirement", section.get("other_requirement"))
        _add_line(lines, "Openings", section.get("openings"))
        _add_line(lines, "Note", section.get("note"))
    return lines


def _render_selection_steps_block(
    steps: list[RecruitingSelectionStepPayload],
) -> list[str]:
    if not steps:
        return []

    lines = ["## Selection Steps"]
    for index, step in enumerate(steps, start=1):
        title = step.get("name") or f"Step {index}"
        lines.append(f"### {title}")
        _add_line(lines, "Schedule", step.get("schedule"))
        _add_line(lines, "Description", step.get("description"))
        _add_line(lines, "Note", step.get("note"))
    return lines


def _render_attachments_block(
    attachments: list[RecruitingAttachmentPayload],
) -> list[str]:
    if not attachments:
        return []

    lines = ["## Attachments"]
    for attachment in attachments:
        lines.append(f"- {attachment['file_name']}")
    return lines


class WorknetRecruitingExternalAdapter:
    """Translate WorkNet recruiting payloads into StrataWiki source envelopes.

    This adapter intentionally stops at SourceRecord. Canonical Fact decomposition
    remains the responsibility of the recruiting domain ingestion plugin.
    """

    connector_name = "worknet"
    domain_name = "recruiting"

    def to_source_record(self, payload: RecruitingSourcePayload) -> SourceRecord:
        posting = payload["posting"]
        source = payload["source"]

        return {
            "source_id": source["source_id"],
            "connector": self.connector_name,
            "domain": self.domain_name,
            "title": posting["title"],
            "body_markdown": self.render_body_markdown(payload),
            "metadata": {
                "payload_version": payload["payload_version"],
                "provider": source["provider"],
                "kind": source["kind"],
                "company_source_id": source.get("company_source_id"),
                "source_url": source.get("source_url"),
                "mobile_source_url": source.get("mobile_source_url"),
                "posting": posting,
                "company": payload.get("company"),
                "jobs": payload["jobs"],
                "recruitment_sections": payload["recruitment_sections"],
                "selection_steps": payload["selection_steps"],
                "attachments": payload["attachments"],
                "raw_included": payload.get("raw") is not None,
            },
            "fetched_at": source["fetched_at"],
            "content_hash": source.get("content_hash") or "",
            "status": "active",
        }

    def fetch_source_record(
        self,
        provider: WorknetRecruitingSourceProvider,
        source_id: str,
        *,
        auth_key: str | None = None,
        include_raw: bool = False,
    ) -> SourceRecord:
        payload = provider.get_recruiting_source(
            {
                "sourceId": source_id,
                "authKey": auth_key,
                "includeRaw": include_raw,
            }
        )
        return self.to_source_record(self._normalize_external_payload(payload))

    def render_body_markdown(self, payload: RecruitingSourcePayload) -> str:
        sections: list[str] = []
        sections.extend(_render_posting_block(payload["posting"]))
        sections.extend([""])
        sections.extend(_render_company_block(payload.get("company")))
        sections.extend([""])
        sections.extend(_render_jobs_block(payload["jobs"]))
        sections.extend([""])
        sections.extend(_render_sections_block(payload["recruitment_sections"]))
        sections.extend([""])
        sections.extend(_render_selection_steps_block(payload["selection_steps"]))
        sections.extend([""])
        sections.extend(_render_attachments_block(payload["attachments"]))

        return "\n".join(line for line in sections if line != "" or (sections and line == ""))

    def _normalize_external_payload(
        self,
        payload: dict[str, Any],
    ) -> RecruitingSourcePayload:
        source = payload["source"]
        posting = payload["posting"]

        return {
            "payload_version": payload["payloadVersion"],
            "source": {
                "provider": source["provider"],
                "kind": source["kind"],
                "source_id": source["sourceId"],
                "company_source_id": source.get("companySourceId"),
                "source_url": source.get("sourceUrl"),
                "mobile_source_url": source.get("mobileSourceUrl"),
                "fetched_at": source["fetchedAt"],
                "content_hash": source.get("contentHash"),
            },
            "posting": {
                "title": posting["title"],
                "company_name": posting["companyName"],
                "company_type": posting.get("companyType"),
                "employment_type": posting.get("employmentType"),
                "starts_at": posting.get("startsAt"),
                "closes_at": posting.get("closesAt"),
                "summary": posting.get("summary"),
                "application_method": posting.get("applicationMethod"),
                "required_documents": posting.get("requiredDocuments"),
                "acceptance_announcement": posting.get("acceptanceAnnouncement"),
                "inquiry": posting.get("inquiry"),
                "notes": posting.get("notes"),
            },
            "company": self._normalize_company_payload(payload.get("company")),
            "jobs": [
                {
                    "source_code": item.get("sourceCode"),
                    "name": item.get("name"),
                }
                for item in payload.get("jobs", [])
            ],
            "recruitment_sections": [
                {
                    "title": item.get("title"),
                    "role_description": item.get("roleDescription"),
                    "selection_description": item.get("selectionDescription"),
                    "location": item.get("location"),
                    "career_requirement": item.get("careerRequirement"),
                    "education_requirement": item.get("educationRequirement"),
                    "other_requirement": item.get("otherRequirement"),
                    "openings": item.get("openings"),
                    "note": item.get("note"),
                }
                for item in payload.get("recruitmentSections", [])
            ],
            "selection_steps": [
                {
                    "name": item.get("name"),
                    "schedule": item.get("schedule"),
                    "description": item.get("description"),
                    "note": item.get("note"),
                }
                for item in payload.get("selectionSteps", [])
            ],
            "attachments": [
                {"file_name": item["fileName"]}
                for item in payload.get("attachments", [])
            ],
            "raw": payload.get("raw"),
        }

    def _normalize_company_payload(
        self,
        company: dict[str, Any] | None,
    ) -> RecruitingCompanyPayload | None:
        if not company:
            return None

        coordinates = company.get("coordinates")
        return {
            "source_company_id": company.get("sourceCompanyId"),
            "name": company["name"],
            "company_type": company.get("companyType"),
            "homepage_url": company.get("homepageUrl"),
            "business_number": company.get("businessNumber"),
            "summary": company.get("summary"),
            "description": company.get("description"),
            "main_business": company.get("mainBusiness"),
            "logo_url": company.get("logoUrl"),
            "coordinates": {
                "latitude": coordinates.get("latitude"),
                "longitude": coordinates.get("longitude"),
            }
            if coordinates
            else None,
        }
