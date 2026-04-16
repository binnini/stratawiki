from __future__ import annotations

from datetime import UTC, datetime

from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.services.interpretation_families.base import InterpretationBuildContext
from wiki_mcp.services.interpretation_families.common import (
    company_name,
    provenance,
    rendered_artifact,
    require_posting,
    snapshot_lines,
    subject_id,
)


class CompanyCandidateProfilePatternBuilder:
    family = "company_candidate_profile_pattern"

    def build_record(
        self,
        context: InterpretationBuildContext,
    ) -> InterpretationRecord | None:
        posting = require_posting(context.facts, self.family)
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
        resolved_company_name = company_name(company=company, posting=posting)
        resolved_subject_id = subject_id(company=company, posting=posting)

        return {
            "id": f"interp:{self.family}:{resolved_subject_id}",
            "domain": context.payload["domain"],
            "kind": self.family,
            "subject_type": "company",
            "subject_id": resolved_subject_id,
            "scope_ref": context.scope_ref,
            "schema_version": context.schema_version,
            "status": "active",
            "confidence": 0.62,
            "computed_at": datetime.now(UTC).isoformat(),
            "expires_at": None,
            "body": {
                "summary": self._build_summary(
                    company_name=resolved_company_name,
                    posting_title=posting_attributes.get("title"),
                    profiled_sections=profiled_sections,
                ),
                "company_name": resolved_company_name,
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
            "provenance": provenance(context),
            "render_hints": {
                "template": self.family,
                "path_hint": f"interpretation/{self.family}/{resolved_subject_id}.md",
            },
        }

    def build_rendered_artifact(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]:
        body = record["body"]
        resolved_company_name = body.get("company_name", record["subject_id"])
        profiled_sections = body.get("profiled_sections", [])
        evidence_fact_ids = body.get("evidence_fact_ids", [])
        lines = [
            f"# {resolved_company_name} candidate profile pattern",
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
        lines.extend(snapshot_lines(snapshot_ref))
        return rendered_artifact(
            record=record,
            title=f"{resolved_company_name} candidate profile pattern",
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
