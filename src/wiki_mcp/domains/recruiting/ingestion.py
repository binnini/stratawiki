from __future__ import annotations

import re
from typing import Any

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.schemas.validation_result import ValidationResult


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str | None) -> str:
    if not value:
        return "unknown"
    normalized = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or "unknown"


def _build_fact_record(
    *,
    record_id: str,
    entity_type: str,
    canonical_key: str,
    attributes: dict[str, Any],
    provenance: dict[str, Any],
) -> FactRecord:
    return {
        "id": record_id,
        "domain": "recruiting",
        "entity_type": entity_type,
        "canonical_key": canonical_key,
        "attributes": attributes,
        "scope": "shared",
        "schema_version": "v1",
        "provenance": provenance,
    }


def _relation_scope_fields(record: FactRecord) -> dict[str, str]:
    scope_fields: dict[str, str] = {"scope": record["scope"]}
    if "tenant_id" in record:
        scope_fields["tenant_id"] = record["tenant_id"]
    if "user_id" in record:
        scope_fields["user_id"] = record["user_id"]
    return scope_fields


class RecruitingSourceIngestionPlugin:
    """Initial recruiting ingestion plugin.

    This plugin intentionally performs only a thin first-pass decomposition from a
    recruiting SourceRecord into a handful of canonical fact envelopes. It is not
    the final recruiting schema.
    """

    domain_name = "recruiting"
    schema_version = "v1"

    def accepts(self, source: SourceRecord) -> bool:
        return source["domain"] == self.domain_name

    def normalize_source(self, source: SourceRecord) -> SourceRecord:
        metadata = dict(source["metadata"])
        metadata.setdefault("posting", {})
        metadata.setdefault("company", None)
        metadata.setdefault("jobs", [])
        metadata.setdefault("recruitment_sections", [])
        metadata.setdefault("selection_steps", [])
        metadata.setdefault("attachments", [])

        return {
            **source,
            "metadata": metadata,
        }

    def extract_fact_records(self, source: SourceRecord) -> list[FactRecord]:
        metadata = source["metadata"]
        posting = metadata["posting"]
        company = metadata.get("company")
        jobs = metadata.get("jobs", [])
        sections = metadata.get("recruitment_sections", [])

        source_id = source["source_id"]
        company_name = posting.get("company_name") or (company or {}).get("name")
        posting_title = posting.get("title") or source["title"]

        posting_key = f"job_posting:{source_id}"
        company_key = (
            f"company:{company.get('source_company_id')}"
            if company and company.get("source_company_id")
            else f"company-name:{_slugify(company_name)}"
        )

        provenance = {
            "source_id": source_id,
            "connector": source["connector"],
            "content_hash": source["content_hash"],
            "fetched_at": source["fetched_at"],
        }

        records: list[FactRecord] = [
            _build_fact_record(
                record_id=f"fact:{posting_key}",
                entity_type="job_posting",
                canonical_key=posting_key,
                attributes={
                    "title": posting_title,
                    "company_name": company_name,
                    "employment_type": posting.get("employment_type"),
                    "starts_at": posting.get("starts_at"),
                    "closes_at": posting.get("closes_at"),
                    "summary": posting.get("summary"),
                    "application_method": posting.get("application_method"),
                    "required_documents": posting.get("required_documents"),
                    "acceptance_announcement": posting.get("acceptance_announcement"),
                    "inquiry": posting.get("inquiry"),
                    "notes": posting.get("notes"),
                },
                provenance=provenance,
            )
        ]

        if company_name:
            records.append(
                _build_fact_record(
                    record_id=f"fact:{company_key}",
                    entity_type="company",
                    canonical_key=company_key,
                    attributes={
                        "name": company_name,
                        "source_company_id": (company or {}).get("source_company_id"),
                        "company_type": (company or {}).get("company_type") or posting.get("company_type"),
                        "homepage_url": (company or {}).get("homepage_url"),
                        "business_number": (company or {}).get("business_number"),
                        "summary": (company or {}).get("summary"),
                        "description": (company or {}).get("description"),
                        "main_business": (company or {}).get("main_business"),
                        "logo_url": (company or {}).get("logo_url"),
                        "coordinates": (company or {}).get("coordinates"),
                    },
                    provenance=provenance,
                )
            )

        for job in jobs:
            job_name = job.get("name")
            job_code = job.get("source_code")
            job_key = f"job:{job_code}" if job_code else f"job-name:{_slugify(job_name)}"
            records.append(
                _build_fact_record(
                    record_id=f"fact:{job_key}",
                    entity_type="job",
                    canonical_key=job_key,
                    attributes={
                        "name": job_name,
                        "source_code": job_code,
                    },
                    provenance=provenance,
                )
            )

        for index, section in enumerate(sections, start=1):
            section_title = section.get("title") or f"section-{index}"
            section_key = f"recruitment_section:{source_id}:{_slugify(section_title)}:{index}"
            records.append(
                _build_fact_record(
                    record_id=f"fact:{section_key}",
                    entity_type="recruitment_section",
                    canonical_key=section_key,
                    attributes={
                        "title": section.get("title"),
                        "role_description": section.get("role_description"),
                        "selection_description": section.get("selection_description"),
                        "location": section.get("location"),
                        "career_requirement": section.get("career_requirement"),
                        "education_requirement": section.get("education_requirement"),
                        "other_requirement": section.get("other_requirement"),
                        "openings": section.get("openings"),
                        "note": section.get("note"),
                    },
                    provenance=provenance,
                )
            )

        return records

    def extract_fact_relations(
        self,
        source: SourceRecord,
        records: list[FactRecord],
    ) -> list[FactRelation]:
        posting_record = next(
            (record for record in records if record["entity_type"] == "job_posting"),
            None,
        )
        if posting_record is None:
            return []

        posting_key = posting_record["canonical_key"]
        provenance = {
            "source_id": source["source_id"],
            "connector": source["connector"],
            "fetched_at": source["fetched_at"],
        }

        relations: list[FactRelation] = []
        for record in records:
            if record["canonical_key"] == posting_key:
                continue

            relation_type = {
                "company": "posted_by",
                "job": "classified_as",
                "recruitment_section": "has_section",
            }.get(record["entity_type"])

            if relation_type is None:
                continue

            relations.append(
                {
                    "domain": self.domain_name,
                    "relation_type": relation_type,
                    "from_canonical_key": posting_key,
                    "to_canonical_key": record["canonical_key"],
                    **_relation_scope_fields(posting_record),
                    "schema_version": self.schema_version,
                    "provenance": provenance,
                }
            )

        return relations

    def validate_batch(
        self,
        source: SourceRecord,
        records: list[FactRecord],
        relations: list[FactRelation],
    ) -> ValidationResult:
        warnings: list[str] = []
        errors: list[str] = []

        if not records:
            errors.append("No recruiting fact records were extracted from source metadata.")

        posting_records = [record for record in records if record["entity_type"] == "job_posting"]
        if len(posting_records) != 1:
            errors.append("Recruiting ingestion expects exactly one job_posting record per source.")

        company_records = [record for record in records if record["entity_type"] == "company"]
        if not company_records:
            warnings.append("No company record was extracted from the recruiting source.")

        job_records = [record for record in records if record["entity_type"] == "job"]
        if not job_records:
            warnings.append("No job classification records were extracted from the recruiting source.")

        if not relations:
            warnings.append("No recruiting fact relations were extracted from the source.")

        return {
            "ok": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
        }
