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
from wiki_mcp.services.interpretation_family_builders import (
    InterpretationBuildContext,
    InterpretationFamilyRegistry,
    build_default_interpretation_family_registry,
)
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
        family_registry: InterpretationFamilyRegistry | None = None,
    ) -> None:
        self.fact_repository = fact_repository
        self.interpretation_repository = interpretation_repository
        self.snapshot_repository = snapshot_repository
        self.dependency_repository = dependency_repository
        self.rendering_repository = rendering_repository
        self.outbox_repository = outbox_repository
        self.family_registry = family_registry or build_default_interpretation_family_registry()

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

    def _build_rendered_artifact(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]:
        return self.family_registry.build_rendered_artifact(
            record,
            snapshot_ref=snapshot_ref,
        )

    def _build_interpretation_records(
        self,
        *,
        payload: FactIngestedPayload,
        facts: list[FactRecord],
        scope_ref: ScopeRef,
        source_event_id: str,
    ) -> list[InterpretationRecord]:
        return self.family_registry.build_records(
            InterpretationBuildContext(
                payload=payload,
                facts=facts,
                scope_ref=scope_ref,
                source_event_id=source_event_id,
                schema_version=self.schema_version,
            )
        )

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
