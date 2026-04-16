from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.outbox_event import FactIngestedPayload
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


@dataclass(frozen=True)
class InterpretationBuildContext:
    payload: FactIngestedPayload
    facts: list[FactRecord]
    scope_ref: ScopeRef
    source_event_id: str
    schema_version: str


class InterpretationFamilyBuilder(Protocol):
    family: str

    def build_record(
        self,
        context: InterpretationBuildContext,
    ) -> InterpretationRecord | None: ...

    def build_rendered_artifact(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]: ...


class InterpretationFamilyRegistry:
    """Kind-aware registry for shared interpretation family builders."""

    def __init__(self, builders: list[InterpretationFamilyBuilder]) -> None:
        self._builders = builders
        self._builders_by_family = {builder.family: builder for builder in builders}

    def build_records(
        self,
        context: InterpretationBuildContext,
    ) -> list[InterpretationRecord]:
        records: list[InterpretationRecord] = []
        for builder in self._builders:
            record = builder.build_record(context)
            if record is not None:
                records.append(record)
        return records

    def build_rendered_artifact(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]:
        builder = self._builders_by_family.get(record["kind"])
        if builder is None:
            raise ValueError(
                f"No interpretation family builder is registered for kind {record['kind']!r}."
            )
        return builder.build_rendered_artifact(record, snapshot_ref=snapshot_ref)


class CompanyHiringPatternBuilder:
    family = "company_hiring_pattern"

    def build_record(
        self,
        context: InterpretationBuildContext,
    ) -> InterpretationRecord:
        posting = _require_posting(context.facts, self.family)
        company = next(
            (fact for fact in context.facts if fact["entity_type"] == "company"),
            None,
        )
        jobs = [fact for fact in context.facts if fact["entity_type"] == "job"]
        sections = [
            fact for fact in context.facts if fact["entity_type"] == "recruitment_section"
        ]

        posting_attributes = posting["attributes"]
        company_name = _company_name(company=company, posting=posting)
        subject_id = _subject_id(company=company, posting=posting)

        return {
            "id": f"interp:{self.family}:{subject_id}",
            "domain": context.payload["domain"],
            "kind": self.family,
            "subject_type": "company",
            "subject_id": subject_id,
            "scope_ref": context.scope_ref,
            "schema_version": context.schema_version,
            "status": "active",
            "confidence": 0.6,
            "computed_at": datetime.now(UTC).isoformat(),
            "expires_at": None,
            "body": {
                "summary": self._build_summary(
                    company_name=company_name,
                    posting_title=posting_attributes.get("title"),
                    jobs=jobs,
                    sections=sections,
                    posting=posting,
                ),
                "company_name": company_name,
                "posting_title": posting_attributes.get("title"),
                "employment_type": posting_attributes.get("employment_type"),
                "job_names": [
                    job["attributes"].get("name")
                    for job in jobs
                    if job["attributes"].get("name")
                ],
                "section_titles": [
                    section["attributes"].get("title")
                    for section in sections
                    if section["attributes"].get("title")
                ],
                "evidence_fact_ids": [fact["id"] for fact in context.facts],
            },
            "provenance": _provenance(context),
            "render_hints": {
                "template": self.family,
                "path_hint": f"interpretation/{self.family}/{subject_id}.md",
            },
        }

    def build_rendered_artifact(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]:
        body = record["body"]
        company_name = body.get("company_name", record["subject_id"])
        job_names = body.get("job_names", [])
        section_titles = body.get("section_titles", [])
        evidence_fact_ids = body.get("evidence_fact_ids", [])
        lines = [
            f"# {company_name} hiring pattern",
            "",
            str(body.get("summary", "")),
            "",
            "## Subject",
            f"- kind: {record['kind']}",
            f"- subject_id: {record['subject_id']}",
        ]
        if body.get("posting_title"):
            lines.append(f"- posting_title: {body['posting_title']}")
        if body.get("employment_type"):
            lines.append(f"- employment_type: {body['employment_type']}")
        if job_names:
            lines.extend(["", "## Job Names", *(f"- {job_name}" for job_name in job_names)])
        if section_titles:
            lines.extend(
                ["", "## Recruitment Sections", *(f"- {title}" for title in section_titles)]
            )
        if evidence_fact_ids:
            lines.extend(
                ["", "## Evidence Facts", *(f"- {fact_id}" for fact_id in evidence_fact_ids)]
            )
        lines.extend(_snapshot_lines(snapshot_ref))
        return _rendered_artifact(
            record=record,
            title=f"{company_name} hiring pattern",
            body_markdown="\n".join(lines),
            snapshot_ref=snapshot_ref,
        )

    def _build_summary(
        self,
        *,
        company_name: str,
        posting_title: object,
        jobs: list[FactRecord],
        sections: list[FactRecord],
        posting: FactRecord,
    ) -> str:
        summary_parts = [f"{company_name} is actively hiring"]
        if posting_title:
            summary_parts.append(f"for {posting_title}")

        job_names = [
            job["attributes"].get("name")
            for job in jobs
            if job["attributes"].get("name")
        ]
        if job_names:
            summary_parts.append(f"across {len(job_names)} classified role(s)")

        section_titles = [
            section["attributes"].get("title")
            for section in sections
            if section["attributes"].get("title")
        ]
        if section_titles:
            summary_parts.append(f"with {len(section_titles)} structured recruitment section(s)")

        employment_type = posting["attributes"].get("employment_type")
        if employment_type:
            summary_parts.append(f"on a {employment_type} basis")

        return " ".join(summary_parts) + "."


class CompanyCandidateProfilePatternBuilder:
    family = "company_candidate_profile_pattern"

    def build_record(
        self,
        context: InterpretationBuildContext,
    ) -> InterpretationRecord | None:
        posting = _require_posting(context.facts, self.family)
        company = next(
            (fact for fact in context.facts if fact["entity_type"] == "company"),
            None,
        )
        profiled_sections = [
            {
                "fact_id": section["id"],
                "title": section["attributes"].get("title"),
                "career_requirement": section["attributes"].get("career_requirement"),
                "education_requirement": section["attributes"].get("education_requirement"),
                "other_requirement": section["attributes"].get("other_requirement"),
                "openings": section["attributes"].get("openings"),
            }
            for section in context.facts
            if section["entity_type"] == "recruitment_section"
            and any(
                section["attributes"].get(field)
                for field in (
                    "career_requirement",
                    "education_requirement",
                    "other_requirement",
                    "openings",
                )
            )
        ]
        if not profiled_sections:
            return None

        posting_attributes = posting["attributes"]
        company_name = _company_name(company=company, posting=posting)
        subject_id = _subject_id(company=company, posting=posting)

        return {
            "id": f"interp:{self.family}:{subject_id}",
            "domain": context.payload["domain"],
            "kind": self.family,
            "subject_type": "company",
            "subject_id": subject_id,
            "scope_ref": context.scope_ref,
            "schema_version": context.schema_version,
            "status": "active",
            "confidence": 0.62,
            "computed_at": datetime.now(UTC).isoformat(),
            "expires_at": None,
            "body": {
                "summary": self._build_summary(
                    company_name=company_name,
                    posting_title=posting_attributes.get("title"),
                    profiled_sections=profiled_sections,
                ),
                "company_name": company_name,
                "posting_title": posting_attributes.get("title"),
                "profiled_sections": profiled_sections,
                "career_requirement_count": sum(
                    1 for section in profiled_sections if section.get("career_requirement")
                ),
                "education_requirement_count": sum(
                    1 for section in profiled_sections if section.get("education_requirement")
                ),
                "other_requirement_count": sum(
                    1 for section in profiled_sections if section.get("other_requirement")
                ),
                "sections_with_openings_count": sum(
                    1 for section in profiled_sections if section.get("openings")
                ),
                "evidence_fact_ids": [fact["id"] for fact in context.facts],
            },
            "provenance": _provenance(context),
            "render_hints": {
                "template": self.family,
                "path_hint": f"interpretation/{self.family}/{subject_id}.md",
            },
        }

    def build_rendered_artifact(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]:
        body = record["body"]
        company_name = body.get("company_name", record["subject_id"])
        profiled_sections = body.get("profiled_sections", [])
        evidence_fact_ids = body.get("evidence_fact_ids", [])
        lines = [
            f"# {company_name} candidate profile pattern",
            "",
            str(body.get("summary", "")),
            "",
            "## Subject",
            f"- kind: {record['kind']}",
            f"- subject_id: {record['subject_id']}",
        ]
        if body.get("posting_title"):
            lines.append(f"- posting_title: {body['posting_title']}")
        lines.extend(
            [
                f"- career_requirement_count: {body.get('career_requirement_count', 0)}",
                f"- education_requirement_count: {body.get('education_requirement_count', 0)}",
                f"- other_requirement_count: {body.get('other_requirement_count', 0)}",
                f"- sections_with_openings_count: {body.get('sections_with_openings_count', 0)}",
            ]
        )
        if profiled_sections:
            lines.extend(["", "## Section Signals"])
            for section in profiled_sections:
                section_title = section.get("title") or section.get("fact_id") or "section"
                lines.append(f"- {section_title}")
                if section.get("career_requirement"):
                    lines.append(f"  - career_requirement: {section['career_requirement']}")
                if section.get("education_requirement"):
                    lines.append(
                        f"  - education_requirement: {section['education_requirement']}"
                    )
                if section.get("other_requirement"):
                    lines.append(f"  - other_requirement: {section['other_requirement']}")
                if section.get("openings"):
                    lines.append(f"  - openings: {section['openings']}")
        if evidence_fact_ids:
            lines.extend(
                ["", "## Evidence Facts", *(f"- {fact_id}" for fact_id in evidence_fact_ids)]
            )
        lines.extend(_snapshot_lines(snapshot_ref))
        return _rendered_artifact(
            record=record,
            title=f"{company_name} candidate profile pattern",
            body_markdown="\n".join(lines),
            snapshot_ref=snapshot_ref,
        )

    def _build_summary(
        self,
        *,
        company_name: str,
        posting_title: object,
        profiled_sections: list[dict[str, object]],
    ) -> str:
        summary_parts = [f"{company_name} is signaling a defined candidate profile"]
        if posting_title:
            summary_parts.append(f"for {posting_title}")
        summary_parts.append(f"across {len(profiled_sections)} recruitment section(s)")

        career_requirement_count = sum(
            1 for section in profiled_sections if section.get("career_requirement")
        )
        education_requirement_count = sum(
            1 for section in profiled_sections if section.get("education_requirement")
        )
        other_requirement_count = sum(
            1 for section in profiled_sections if section.get("other_requirement")
        )
        openings_count = sum(1 for section in profiled_sections if section.get("openings"))

        if career_requirement_count:
            summary_parts.append(
                f"with explicit career expectations in {career_requirement_count} section(s)"
            )
        if education_requirement_count:
            summary_parts.append(
                f"education requirements in {education_requirement_count} section(s)"
            )
        if other_requirement_count:
            summary_parts.append(
                f"additional requirements in {other_requirement_count} section(s)"
            )
        if openings_count:
            summary_parts.append(f"and opening counts in {openings_count} section(s)")

        return " ".join(summary_parts) + "."


def build_default_interpretation_family_registry() -> InterpretationFamilyRegistry:
    return InterpretationFamilyRegistry(
        [
            CompanyHiringPatternBuilder(),
            CompanyCandidateProfilePatternBuilder(),
        ]
    )


def _company_name(*, company: FactRecord | None, posting: FactRecord) -> object:
    return (
        (company["attributes"].get("name") if company else None)
        or posting["attributes"].get("company_name")
        or "unknown"
    )


def _subject_id(*, company: FactRecord | None, posting: FactRecord) -> str:
    return company["canonical_key"] if company else posting["canonical_key"]


def _require_posting(facts: list[FactRecord], family: str) -> FactRecord:
    posting = next((fact for fact in facts if fact["entity_type"] == "job_posting"), None)
    if posting is None:
        raise ValueError(
            f"{family} projection requires a job_posting fact in the affected batch."
        )
    return posting


def _provenance(context: InterpretationBuildContext) -> dict[str, object]:
    return {
        "source_event_id": context.source_event_id,
        "fact_snapshot_id": context.payload["fact_snapshot_id"],
        "source_id": context.payload["source_id"],
        "connector": context.payload["connector"],
        "evidence_fact_ids": [fact["id"] for fact in context.facts],
    }


def _rendered_artifact(
    *,
    record: InterpretationRecord,
    title: str,
    body_markdown: str,
    snapshot_ref: SnapshotRef,
) -> dict[str, object]:
    return {
        "domain": record["domain"],
        "layer": "interpretation",
        "record_id": record["id"],
        "path": _rendered_path_for_record(record),
        "title": title,
        "body_markdown": body_markdown,
        "scope_ref": record["scope_ref"],
        "snapshot_ref": snapshot_ref,
    }


def _rendered_path_for_record(record: InterpretationRecord) -> str:
    subject_key = record["subject_id"].replace(":", "__")
    return f"wiki/shared/{record['domain']}/{record['kind']}/{subject_key}.md"


def _snapshot_lines(snapshot_ref: SnapshotRef) -> list[str]:
    return [
        "",
        "## Snapshot Provenance",
        f"- fact_snapshot_id: {snapshot_ref['fact_snapshot_id']}",
        f"- interpretation_snapshot_id: {snapshot_ref.get('interpretation_snapshot_id', '')}",
    ]
