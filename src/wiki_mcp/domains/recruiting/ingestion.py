from __future__ import annotations

import hashlib
import re
from typing import Any

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.schemas.validation_result import ValidationResult


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SKILL_TOKEN_RE = re.compile(r"[A-Za-z0-9.+#/\\-]+")


def _slugify(value: str | None) -> str:
    if not value:
        return "unknown"
    stripped = value.strip().lower()
    normalized = _SLUG_RE.sub("-", stripped).strip("-")
    if normalized:
        return normalized

    return "text-" + hashlib.sha1(stripped.encode("utf-8")).hexdigest()[:12]


def _normalize_whitespace(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = " ".join(value.split()).strip()
    return normalized or None


def _dedupe_records(records: list[FactRecord]) -> list[FactRecord]:
    by_identity: dict[tuple[str, str], FactRecord] = {}
    for record in records:
        identity = (record["entity_type"], record["canonical_key"])
        by_identity.setdefault(identity, record)
    return list(by_identity.values())


def _dedupe_relations(relations: list[FactRelation]) -> list[FactRelation]:
    by_identity: dict[tuple[str, str, str], FactRelation] = {}
    for relation in relations:
        identity = (
            relation["relation_type"],
            relation["from_canonical_key"],
            relation["to_canonical_key"],
        )
        by_identity.setdefault(identity, relation)
    return list(by_identity.values())


def _extract_skill_names(*texts: str | None) -> list[str]:
    skills: dict[str, str] = {}

    for text in texts:
        normalized_text = _normalize_whitespace(text)
        if not normalized_text:
            continue

        for token in _SKILL_TOKEN_RE.findall(normalized_text):
            stripped = token.strip(".,:;()[]{}<>")
            if len(stripped) < 2:
                continue
            if not any(character.isalpha() for character in stripped):
                continue

            lowered = stripped.lower()
            if lowered in {"api", "and", "or"}:
                continue

            skills.setdefault(lowered, stripped)

    return list(skills.values())


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
        "schema_version": "fact.v1",
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
    schema_version = "fact.v1"

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
        source_url = metadata.get("source_url")
        mobile_source_url = metadata.get("mobile_source_url")

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
                    "source_url": source_url,
                    "mobile_source_url": mobile_source_url,
                    "status": source["status"],
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
                        "normalized_name": _normalize_whitespace(company_name.lower()) if company_name else None,
                        "source_company_id": (company or {}).get("source_company_id"),
                        "company_type": (company or {}).get("company_type")
                        or posting.get("company_type"),
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

        role_seed_items = jobs or [{"name": posting_title, "source_code": None}]
        for job in role_seed_items:
            role_name = _normalize_whitespace(job.get("name")) or posting_title
            role_code = job.get("source_code")
            role_key = f"role:{role_code}" if role_code else f"role-name:{_slugify(role_name)}"
            records.append(
                _build_fact_record(
                    record_id=f"fact:{role_key}",
                    entity_type="role",
                    canonical_key=role_key,
                    attributes={
                        "display_name": role_name,
                        "normalized_name": _normalize_whitespace(role_name.lower()),
                        "source_code": role_code,
                    },
                    provenance=provenance,
                )
            )

        for section in sections:
            location_name = _normalize_whitespace(section.get("location"))
            if not location_name:
                continue

            location_key = f"location:{_slugify(location_name)}"
            records.append(
                _build_fact_record(
                    record_id=f"fact:{location_key}",
                    entity_type="location",
                    canonical_key=location_key,
                    attributes={
                        "label": location_name,
                    },
                    provenance=provenance,
                )
            )

        skill_names = _extract_skill_names(
            posting.get("summary"),
            posting.get("notes"),
            *[section.get("role_description") for section in sections],
            *[section.get("other_requirement") for section in sections],
        )
        for skill_name in skill_names:
            skill_key = f"skill:{_slugify(skill_name)}"
            records.append(
                _build_fact_record(
                    record_id=f"fact:{skill_key}",
                    entity_type="skill",
                    canonical_key=skill_key,
                    attributes={
                        "name": skill_name,
                        "normalized_name": skill_name.lower(),
                    },
                    provenance=provenance,
                )
            )

        return _dedupe_records(records)

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
                "role": "has_role",
                "skill": "requires_skill",
                "location": "located_in",
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

        return _dedupe_relations(relations)

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

        role_records = [record for record in records if record["entity_type"] == "role"]
        if not role_records:
            warnings.append("No role records were extracted from the recruiting source.")

        skill_records = [record for record in records if record["entity_type"] == "skill"]
        if not skill_records:
            warnings.append("No skill records were extracted from the recruiting source.")

        if not relations:
            warnings.append("No recruiting fact relations were extracted from the source.")

        return {
            "ok": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
        }
