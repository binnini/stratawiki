from __future__ import annotations

from datetime import UTC, datetime

from wiki_mcp.schemas.fact_record import FactRecord
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


class CompanyHiringPatternBuilder:
    family = "company_hiring_pattern"

    def build_record(
        self,
        context: InterpretationBuildContext,
    ) -> InterpretationRecord:
        posting = require_posting(context.facts, self.family)
        company = next(
            (fact for fact in context.facts if fact["entity_type"] == "company"),
            None,
        )
        jobs = [fact for fact in context.facts if fact["entity_type"] == "job"]
        sections = [
            fact for fact in context.facts if fact["entity_type"] == "recruitment_section"
        ]

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
            "confidence": 0.6,
            "computed_at": datetime.now(UTC).isoformat(),
            "expires_at": None,
            "body": {
                "summary": self._build_summary(
                    company_name=resolved_company_name,
                    posting_title=posting_attributes.get("title"),
                    jobs=jobs,
                    sections=sections,
                    posting=posting,
                ),
                "company_name": resolved_company_name,
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
        job_names = body.get("job_names", [])
        section_titles = body.get("section_titles", [])
        evidence_fact_ids = body.get("evidence_fact_ids", [])
        lines = [
            f"# {resolved_company_name} hiring pattern",
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
        lines.extend(snapshot_lines(snapshot_ref))
        return rendered_artifact(
            record=record,
            title=f"{resolved_company_name} hiring pattern",
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
