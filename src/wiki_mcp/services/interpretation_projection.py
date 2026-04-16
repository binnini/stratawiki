from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from wiki_mcp.schemas.dependency_edge import DependencyEdge
from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.interpretation_projection_result import (
    InterpretationProjectionResult,
)
from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.outbox_event import (
    FactIngestedPayload,
    InterpretationSnapshotPublishedPayload,
    OutboxEvent,
    OutboxEventRecord,
)
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.services.interfaces.repositories import (
    DependencyRepository,
    FactRepository,
    InterpretationRepository,
    OutboxRepository,
    RenderingRepository,
    SnapshotRepository,
)


class DefaultInterpretationProjectionService:
    """Deterministic first Interpretation projection over ingested recruiting facts."""

    schema_version = "v1"

    def __init__(
        self,
        *,
        fact_repository: FactRepository,
        interpretation_repository: InterpretationRepository,
        snapshot_repository: SnapshotRepository,
        dependency_repository: DependencyRepository,
        rendering_repository: RenderingRepository,
        outbox_repository: OutboxRepository,
    ) -> None:
        self.fact_repository = fact_repository
        self.interpretation_repository = interpretation_repository
        self.snapshot_repository = snapshot_repository
        self.dependency_repository = dependency_repository
        self.rendering_repository = rendering_repository
        self.outbox_repository = outbox_repository

    def project_fact_event(
        self,
        event: OutboxEventRecord,
    ) -> InterpretationProjectionResult:
        if event["event_type"] != "fact_ingested":
            raise ValueError(
                f"Unsupported outbox event type for interpretation projection: {event['event_type']!r}."
            )

        payload = self._parse_fact_ingested_payload(event["payload"])
        scope_ref = self._scope_ref_from_payload(payload)
        facts = self.fact_repository.get_by_ids(payload["affected_fact_ids"], scope_ref)
        if not facts:
            raise ValueError(
                f"Fact snapshot {payload['fact_snapshot_id']!r} did not load any fact records."
            )

        interpretation_records = self._build_interpretation_records(
            payload=payload,
            facts=facts,
            scope_ref=scope_ref,
            source_event_id=event["id"],
        )
        stored_ids = self.interpretation_repository.save_records(
            interpretation_records,
            {"fact_snapshot_id": payload["fact_snapshot_id"]},
        )
        stored_record_ids = {
            record["id"]: record for record in interpretation_records
        }

        for interpretation_id in stored_ids:
            self.dependency_repository.replace_edges_for_target(
                domain=payload["domain"],
                to_layer="interpretation",
                to_id=interpretation_id,
                scope_ref=scope_ref,
                edges=[
                    self._build_dependency_edge(
                        domain=payload["domain"],
                        fact=fact,
                        interpretation_id=interpretation_id,
                        scope_ref=scope_ref,
                    )
                    for fact in facts
                ],
            )

        interpretation_snapshot_id = self._new_interpretation_snapshot_id(payload["domain"])
        snapshot_ref: SnapshotRef = {
            "fact_snapshot_id": payload["fact_snapshot_id"],
            "interpretation_snapshot_id": interpretation_snapshot_id,
        }
        self.snapshot_repository.publish_snapshot(
            "interpretation",
            payload["domain"],
            snapshot_ref,
        )

        for interpretation_id in stored_ids:
            self.rendering_repository.write_artifact(
                self._build_rendered_artifact(
                    stored_record_ids[interpretation_id],
                    snapshot_ref=snapshot_ref,
                )
            )
        emitted_outbox_event_ids = self.outbox_repository.append_events(
            [
                self._build_interpretation_snapshot_published_event(
                    payload=payload,
                    interpretation_snapshot_id=interpretation_snapshot_id,
                    interpretation_kind=stored_record_ids[interpretation_id]["kind"],
                    interpretation_ids=[interpretation_id],
                    source_event_id=event["id"],
                )
                for interpretation_id in stored_ids
            ]
        )

        return {
            "fact_snapshot_id": payload["fact_snapshot_id"],
            "interpretation_snapshot_id": interpretation_snapshot_id,
            "interpretation_ids": stored_ids,
            "emitted_outbox_event_ids": emitted_outbox_event_ids,
        }

    def _parse_fact_ingested_payload(
        self,
        payload: dict[str, object],
    ) -> FactIngestedPayload:
        required_keys = {
            "domain",
            "source_id",
            "connector",
            "fact_snapshot_id",
            "affected_fact_ids",
            "affected_entity_types",
            "scope",
            "facts_created",
            "facts_updated",
            "relations_created",
        }
        missing_keys = sorted(key for key in required_keys if key not in payload)
        if missing_keys:
            raise ValueError(
                "fact_ingested payload is missing required fields: "
                + ", ".join(missing_keys)
            )
        return payload  # type: ignore[return-value]

    def _scope_ref_from_payload(self, payload: FactIngestedPayload) -> ScopeRef:
        scope_ref: ScopeRef = {"scope": payload["scope"]}
        if "tenant_id" in payload:
            scope_ref["tenant_id"] = payload["tenant_id"]
        if "user_id" in payload:
            scope_ref["user_id"] = payload["user_id"]
        return scope_ref

    def _build_company_hiring_pattern(
        self,
        *,
        payload: FactIngestedPayload,
        facts: list[FactRecord],
        scope_ref: ScopeRef,
        source_event_id: str,
    ) -> InterpretationRecord:
        posting = next((fact for fact in facts if fact["entity_type"] == "job_posting"), None)
        if posting is None:
            raise ValueError(
                "company_hiring_pattern projection requires a job_posting fact in the affected batch."
            )

        company = next((fact for fact in facts if fact["entity_type"] == "company"), None)
        jobs = [fact for fact in facts if fact["entity_type"] == "job"]
        sections = [fact for fact in facts if fact["entity_type"] == "recruitment_section"]

        posting_attributes = posting["attributes"]
        company_name = (
            (company["attributes"].get("name") if company else None)
            or posting_attributes.get("company_name")
            or "unknown"
        )
        subject_id = company["canonical_key"] if company else posting["canonical_key"]
        computed_at = datetime.now(UTC).isoformat()
        summary = self._build_summary(
            company_name=company_name,
            posting_title=posting_attributes.get("title"),
            jobs=jobs,
            sections=sections,
            posting=posting,
        )

        return {
            "id": f"interp:company_hiring_pattern:{subject_id}",
            "domain": payload["domain"],
            "kind": "company_hiring_pattern",
            "subject_type": "company",
            "subject_id": subject_id,
            "scope_ref": scope_ref,
            "schema_version": self.schema_version,
            "status": "active",
            "confidence": 0.6,
            "computed_at": computed_at,
            "expires_at": None,
            "body": {
                "summary": summary,
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
                "evidence_fact_ids": [fact["id"] for fact in facts],
            },
            "provenance": {
                "source_event_id": source_event_id,
                "fact_snapshot_id": payload["fact_snapshot_id"],
                "source_id": payload["source_id"],
                "connector": payload["connector"],
                "evidence_fact_ids": [fact["id"] for fact in facts],
            },
            "render_hints": {
                "template": "company_hiring_pattern",
                "path_hint": f"interpretation/company_hiring_pattern/{subject_id}.md",
            },
        }

    def _build_company_candidate_profile_pattern(
        self,
        *,
        payload: FactIngestedPayload,
        facts: list[FactRecord],
        scope_ref: ScopeRef,
        source_event_id: str,
    ) -> InterpretationRecord | None:
        posting = next((fact for fact in facts if fact["entity_type"] == "job_posting"), None)
        if posting is None:
            raise ValueError(
                "company_candidate_profile_pattern projection requires a job_posting fact in the affected batch."
            )

        company = next((fact for fact in facts if fact["entity_type"] == "company"), None)
        sections = [fact for fact in facts if fact["entity_type"] == "recruitment_section"]
        profiled_sections = [
            {
                "fact_id": section["id"],
                "title": section["attributes"].get("title"),
                "career_requirement": section["attributes"].get("career_requirement"),
                "education_requirement": section["attributes"].get("education_requirement"),
                "other_requirement": section["attributes"].get("other_requirement"),
                "openings": section["attributes"].get("openings"),
            }
            for section in sections
            if any(
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
        company_name = (
            (company["attributes"].get("name") if company else None)
            or posting_attributes.get("company_name")
            or "unknown"
        )
        subject_id = company["canonical_key"] if company else posting["canonical_key"]
        computed_at = datetime.now(UTC).isoformat()
        summary = self._build_candidate_profile_summary(
            company_name=company_name,
            posting_title=posting_attributes.get("title"),
            profiled_sections=profiled_sections,
        )

        return {
            "id": f"interp:company_candidate_profile_pattern:{subject_id}",
            "domain": payload["domain"],
            "kind": "company_candidate_profile_pattern",
            "subject_type": "company",
            "subject_id": subject_id,
            "scope_ref": scope_ref,
            "schema_version": self.schema_version,
            "status": "active",
            "confidence": 0.62,
            "computed_at": computed_at,
            "expires_at": None,
            "body": {
                "summary": summary,
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
                "evidence_fact_ids": [fact["id"] for fact in facts],
            },
            "provenance": {
                "source_event_id": source_event_id,
                "fact_snapshot_id": payload["fact_snapshot_id"],
                "source_id": payload["source_id"],
                "connector": payload["connector"],
                "evidence_fact_ids": [fact["id"] for fact in facts],
            },
            "render_hints": {
                "template": "company_candidate_profile_pattern",
                "path_hint": f"interpretation/company_candidate_profile_pattern/{subject_id}.md",
            },
        }

    def _build_rendered_artifact(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]:
        if record["kind"] == "company_candidate_profile_pattern":
            return self._build_company_candidate_profile_rendered_artifact(
                record,
                snapshot_ref=snapshot_ref,
            )

        return self._build_company_hiring_pattern_rendered_artifact(
            record,
            snapshot_ref=snapshot_ref,
        )

    def _build_company_hiring_pattern_rendered_artifact(
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
            lines.extend(
                [
                    "",
                    "## Job Names",
                    *(f"- {job_name}" for job_name in job_names),
                ]
            )
        if section_titles:
            lines.extend(
                [
                    "",
                    "## Recruitment Sections",
                    *(f"- {title}" for title in section_titles),
                ]
            )
        if evidence_fact_ids:
            lines.extend(
                [
                    "",
                    "## Evidence Facts",
                    *(f"- {fact_id}" for fact_id in evidence_fact_ids),
                ]
            )
        lines.extend(
            [
                "",
                "## Snapshot Provenance",
                f"- fact_snapshot_id: {snapshot_ref['fact_snapshot_id']}",
                f"- interpretation_snapshot_id: {snapshot_ref.get('interpretation_snapshot_id', '')}",
            ]
        )
        return {
            "domain": record["domain"],
            "layer": "interpretation",
            "record_id": record["id"],
            "path": self._rendered_path_for_record(record),
            "title": f"{company_name} hiring pattern",
            "body_markdown": "\n".join(lines),
            "scope_ref": record["scope_ref"],
            "snapshot_ref": snapshot_ref,
        }

    def _build_company_candidate_profile_rendered_artifact(
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
                [
                    "",
                    "## Evidence Facts",
                    *(f"- {fact_id}" for fact_id in evidence_fact_ids),
                ]
            )
        lines.extend(
            [
                "",
                "## Snapshot Provenance",
                f"- fact_snapshot_id: {snapshot_ref['fact_snapshot_id']}",
                f"- interpretation_snapshot_id: {snapshot_ref.get('interpretation_snapshot_id', '')}",
            ]
        )
        return {
            "domain": record["domain"],
            "layer": "interpretation",
            "record_id": record["id"],
            "path": self._rendered_path_for_record(record),
            "title": f"{company_name} candidate profile pattern",
            "body_markdown": "\n".join(lines),
            "scope_ref": record["scope_ref"],
            "snapshot_ref": snapshot_ref,
        }

    def _rendered_path_for_record(self, record: InterpretationRecord) -> str:
        subject_key = record["subject_id"].replace(":", "__")
        return (
            f"wiki/shared/{record['domain']}/{record['kind']}/{subject_key}.md"
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

    def _build_candidate_profile_summary(
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

    def _build_interpretation_records(
        self,
        *,
        payload: FactIngestedPayload,
        facts: list[FactRecord],
        scope_ref: ScopeRef,
        source_event_id: str,
    ) -> list[InterpretationRecord]:
        records = [
            self._build_company_hiring_pattern(
                payload=payload,
                facts=facts,
                scope_ref=scope_ref,
                source_event_id=source_event_id,
            )
        ]

        candidate_profile_record = self._build_company_candidate_profile_pattern(
            payload=payload,
            facts=facts,
            scope_ref=scope_ref,
            source_event_id=source_event_id,
        )
        if candidate_profile_record is not None:
            records.append(candidate_profile_record)

        return records

    def _build_dependency_edge(
        self,
        *,
        domain: str,
        fact: FactRecord,
        interpretation_id: str,
        scope_ref: ScopeRef,
    ) -> DependencyEdge:
        return {
            "domain": domain,
            "from_layer": "fact",
            "from_id": fact["id"],
            "to_layer": "interpretation",
            "to_id": interpretation_id,
            "scope_ref": scope_ref,
            "edge_type": "derived_from",
            "attributes": {
                "fact_entity_type": fact["entity_type"],
            },
        }

    def _build_interpretation_snapshot_published_event(
        self,
        *,
        payload: FactIngestedPayload,
        interpretation_snapshot_id: str,
        interpretation_kind: str,
        interpretation_ids: list[str],
        source_event_id: str,
    ) -> OutboxEvent:
        event_payload: InterpretationSnapshotPublishedPayload = {
            "domain": payload["domain"],
            "interpretation_kind": interpretation_kind,
            "fact_snapshot_id": payload["fact_snapshot_id"],
            "interpretation_snapshot_id": interpretation_snapshot_id,
            "interpretation_ids": interpretation_ids,
            "source_event_id": source_event_id,
            "scope": payload["scope"],
            **({"tenant_id": payload["tenant_id"]} if "tenant_id" in payload else {}),
            **({"user_id": payload["user_id"]} if "user_id" in payload else {}),
        }
        return {
            "event_type": "interpretation_snapshot_published",
            "aggregate_layer": "interpretation",
            "aggregate_id": interpretation_snapshot_id,
            "idempotency_key": (
                f"interpretation_snapshot_published:"
                f"{payload['domain']}:{interpretation_kind}:{payload['fact_snapshot_id']}"
            ),
            "payload": event_payload,
        }

    def _new_interpretation_snapshot_id(self, domain: str) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"interp_snap:{domain}:shared_projection:{timestamp}:{uuid4().hex[:8]}"


class DefaultOutboxProjectionWorker:
    """Small synchronous worker for the first projection path."""

    def __init__(
        self,
        *,
        outbox_repository: OutboxRepository,
        interpretation_projection_service: DefaultInterpretationProjectionService,
    ) -> None:
        self.outbox_repository = outbox_repository
        self.interpretation_projection_service = interpretation_projection_service

    def run_once(self, *, limit: int = 10) -> list[InterpretationProjectionResult]:
        claimed_events = self.outbox_repository.claim_pending(
            limit=limit,
            event_types=["fact_ingested"],
        )
        results: list[InterpretationProjectionResult] = []

        for event in claimed_events:
            try:
                result = self.interpretation_projection_service.project_fact_event(event)
            except ValueError as exc:
                self.outbox_repository.mark_failed(
                    event["id"],
                    str(exc),
                    retryable=False,
                )
                continue
            except Exception as exc:
                self.outbox_repository.mark_failed(event["id"], str(exc))
                continue

            self.outbox_repository.mark_processed(event["id"])
            results.append(result)

        return results
