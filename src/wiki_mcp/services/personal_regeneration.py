from __future__ import annotations

from typing import cast

from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.outbox_event import (
    OutboxEvent,
    OutboxEventRecord,
    PersonalRecordsMarkedStalePayload,
    PersonalRecordsRegeneratedPayload,
)
from wiki_mcp.schemas.personal_record import PersonalRecord
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.services.interfaces.repositories import (
    InterpretationRepository,
    OutboxRepository,
    PersonalRepository,
    ProfileContextRepository,
    RenderingRepository,
)


class DefaultPersonalRegenerationService:
    """Regenerate stale Personal records from current profile and shared interpretation state."""

    def __init__(
        self,
        *,
        personal_repository: PersonalRepository,
        profile_context_repository: ProfileContextRepository,
        interpretation_repository: InterpretationRepository,
        rendering_repository: RenderingRepository,
        outbox_repository: OutboxRepository,
    ) -> None:
        self.personal_repository = personal_repository
        self.profile_context_repository = profile_context_repository
        self.interpretation_repository = interpretation_repository
        self.rendering_repository = rendering_repository
        self.outbox_repository = outbox_repository

    def regenerate_from_stale_event(
        self,
        event: OutboxEventRecord,
    ) -> list[str]:
        if event["event_type"] != "personal_records_marked_stale":
            raise ValueError(
                "Unsupported outbox event type for personal regeneration: "
                f"{event['event_type']!r}."
            )

        payload = self._parse_payload(event["payload"])
        scope_ref = self._scope_ref_from_payload(payload)
        personal_records = self.personal_repository.get_by_ids(
            payload["personal_record_ids"],
            scope_ref,
        )
        if not personal_records:
            raise ValueError("No Personal records found for regeneration event.")

        interpretations = self.interpretation_repository.get_by_ids(
            payload["triggering_interpretation_ids"],
            scope_ref,
        )
        if not interpretations:
            raise ValueError("No Interpretation records found for Personal regeneration.")

        regenerated_ids: list[str] = []
        profile_cache: dict[tuple[str, str, str], ProfileContext] = {}

        for record in personal_records:
            record_scope_ref = record["scope_ref"]
            if record_scope_ref["scope"] != "user":
                raise ValueError(
                    f"Personal regeneration currently requires user scope, got {record_scope_ref['scope']!r}."
                )

            tenant_id = record_scope_ref["tenant_id"]
            user_id = record_scope_ref["user_id"]
            cache_key = (record["domain"], tenant_id, user_id)
            profile_context = profile_cache.get(cache_key)
            if profile_context is None:
                profile_context = self.profile_context_repository.get_profile_context(
                    record["domain"],
                    tenant_id,
                    user_id,
                )
                profile_cache[cache_key] = profile_context

            refreshed_record = self._build_refreshed_record(
                record,
                payload=payload,
                profile_context=profile_context,
                interpretations=interpretations,
                source_event_id=event["id"],
            )
            artifact = self._build_rendered_artifact(
                refreshed_record,
                profile_context=profile_context,
                interpretations=interpretations,
            )
            self.rendering_repository.write_artifact(artifact)
            self.personal_repository.save_record(refreshed_record)
            regenerated_ids.append(refreshed_record["id"])

        self.outbox_repository.append_events(
            [
                self._build_regenerated_event(
                    payload=payload,
                    profile_version=profile_cache[next(iter(profile_cache))]["profile_version"],
                    personal_record_ids=regenerated_ids,
                    source_event_id=event["id"],
                )
            ]
        )
        return regenerated_ids

    def _parse_payload(
        self,
        payload: dict[str, object],
    ) -> PersonalRecordsMarkedStalePayload:
        required_keys = {
            "domain",
            "fact_snapshot_id",
            "interpretation_snapshot_id",
            "personal_record_ids",
            "triggering_interpretation_ids",
            "source_event_id",
            "scope",
        }
        missing_keys = sorted(key for key in required_keys if key not in payload)
        if missing_keys:
            raise ValueError(
                "personal_records_marked_stale payload is missing required fields: "
                + ", ".join(missing_keys)
            )
        return cast(PersonalRecordsMarkedStalePayload, payload)

    def _scope_ref_from_payload(
        self,
        payload: PersonalRecordsMarkedStalePayload,
    ) -> ScopeRef:
        scope_ref: ScopeRef = {"scope": payload["scope"]}
        if "tenant_id" in payload:
            scope_ref["tenant_id"] = payload["tenant_id"]
        if "user_id" in payload:
            scope_ref["user_id"] = payload["user_id"]
        return scope_ref

    def _build_refreshed_record(
        self,
        record: PersonalRecord,
        *,
        payload: PersonalRecordsMarkedStalePayload,
        profile_context: ProfileContext,
        interpretations: list[InterpretationRecord],
        source_event_id: str,
    ) -> PersonalRecord:
        summary = self._build_summary(record, profile_context, interpretations)
        return {
            **record,
            "summary": summary,
            "snapshot_ref": {
                "fact_snapshot_id": payload["fact_snapshot_id"],
                "interpretation_snapshot_id": payload["interpretation_snapshot_id"],
                "profile_version": profile_context["profile_version"],
            },
            "profile_version": profile_context["profile_version"],
            "status": "active",
            "provenance": {
                **record["provenance"],
                "regeneration": {
                    "source_event_id": source_event_id,
                    "triggering_interpretation_ids": payload["triggering_interpretation_ids"],
                    "fact_snapshot_id": payload["fact_snapshot_id"],
                    "interpretation_snapshot_id": payload["interpretation_snapshot_id"],
                    "profile_version": profile_context["profile_version"],
                },
            },
        }

    def _build_rendered_artifact(
        self,
        record: PersonalRecord,
        *,
        profile_context: ProfileContext,
        interpretations: list[InterpretationRecord],
    ) -> RenderedArtifact:
        body_lines = [
            f"# {record['title']}",
            "",
            record["summary"],
            "",
            "## Profile Goals",
            *(f"- {goal}" for goal in profile_context["goals"]),
            "",
            "## Shared Interpretations",
        ]
        for interpretation in interpretations:
            body_lines.append(
                f"- {interpretation['kind']}: {interpretation['body'].get('summary', interpretation['subject_id'])}"
            )
        body_lines.extend(
            [
                "",
                "## Snapshot Provenance",
                f"- fact_snapshot_id: {record['snapshot_ref']['fact_snapshot_id']}",
                f"- interpretation_snapshot_id: {record['snapshot_ref'].get('interpretation_snapshot_id', '')}",
                f"- profile_version: {record['profile_version']}",
            ]
        )
        return {
            "domain": record["domain"],
            "layer": "personal",
            "record_id": record["id"],
            "path": record["body_path"],
            "title": record["title"],
            "body_markdown": "\n".join(body_lines),
            "scope_ref": record["scope_ref"],
            "snapshot_ref": record["snapshot_ref"],
        }

    def _build_summary(
        self,
        record: PersonalRecord,
        profile_context: ProfileContext,
        interpretations: list[InterpretationRecord],
    ) -> str:
        goals = ", ".join(profile_context["goals"][:2]) or "current goals"
        interpretations_summary = "; ".join(
            interpretation["body"].get("summary", interpretation["subject_id"])
            for interpretation in interpretations[:2]
        )
        if not interpretations_summary:
            interpretations_summary = "shared recruiting interpretations"
        return (
            f"Refreshed {record['kind'].replace('_', ' ')} for {goals}. "
            f"Grounded in {interpretations_summary}."
        )

    def _build_regenerated_event(
        self,
        *,
        payload: PersonalRecordsMarkedStalePayload,
        profile_version: str,
        personal_record_ids: list[str],
        source_event_id: str,
    ) -> OutboxEvent:
        event_payload: PersonalRecordsRegeneratedPayload = {
            "domain": payload["domain"],
            "fact_snapshot_id": payload["fact_snapshot_id"],
            "interpretation_snapshot_id": payload["interpretation_snapshot_id"],
            "profile_version": profile_version,
            "personal_record_ids": personal_record_ids,
            "source_event_id": source_event_id,
            "scope": payload["scope"],
            **({"tenant_id": payload["tenant_id"]} if "tenant_id" in payload else {}),
            **({"user_id": payload["user_id"]} if "user_id" in payload else {}),
        }
        return {
            "event_type": "personal_records_regenerated",
            "aggregate_layer": "personal",
            "aggregate_id": payload["interpretation_snapshot_id"],
            "idempotency_key": (
                "personal_records_regenerated:"
                f"{payload['interpretation_snapshot_id']}"
            ),
            "payload": event_payload,
        }


class DefaultPersonalRegenerationWorker:
    """Small synchronous worker for Personal regeneration."""

    def __init__(
        self,
        *,
        outbox_repository: OutboxRepository,
        personal_regeneration_service: DefaultPersonalRegenerationService,
    ) -> None:
        self.outbox_repository = outbox_repository
        self.personal_regeneration_service = personal_regeneration_service

    def run_once(self, *, limit: int = 10) -> list[list[str]]:
        claimed_events = self.outbox_repository.claim_pending(
            limit=limit,
            event_types=["personal_records_marked_stale"],
        )
        results: list[list[str]] = []

        for event in claimed_events:
            try:
                result = self.personal_regeneration_service.regenerate_from_stale_event(
                    event
                )
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
