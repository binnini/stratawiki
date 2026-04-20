from __future__ import annotations

from pathlib import Path
from typing import Any

from wiki_mcp.services import (
    InterpretationProposalService,
    InterpretationPublicationService,
    InterpretationQueryService,
)
from wiki_mcp.services.interpretation_rendering import InterpretationRenderingService
from wiki_mcp.services.interpretation_families import (
    InterpretationFamilyRegistry,
)
from wiki_mcp.storage.filesystem import FileSystemRenderingRepository


class FakeInterpretationRepository:
    def __init__(self, records: dict[str, dict[str, Any]] | None = None) -> None:
        self.records = dict(records or {})
        self.saved_batches: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [dict(self.records[record_id]) for record_id in ids if record_id in self.records]

    def list_records(
        self,
        *,
        domain: str,
        scope_ref: dict[str, Any],
        family: str | None = None,
        kind: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for record in self.records.values():
            if record["domain"] != domain:
                continue
            if family is not None and record.get("family") != family:
                continue
            if kind is not None and record.get("kind") != kind:
                continue
            if subject_type is not None and record.get("subject_type") != subject_type:
                continue
            if subject_id is not None and record.get("subject_id") != subject_id:
                continue
            if statuses and record.get("status") not in statuses:
                continue
            matches.append(dict(record))
        return matches[:limit]

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: dict[str, Any],
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        lowered = query_text.lower()
        for record in self.records.values():
            haystack = " ".join(
                str(record.get(key, ""))
                for key in ("title", "claim", "summary", "subject_id", "kind", "family")
            ).lower()
            if record["domain"] != domain or record.get("status") not in {"published", "stale"}:
                continue
            if lowered and lowered not in haystack and not any(token in haystack for token in query_tokens):
                continue
            matches.append(dict(record))
        return matches[:limit]

    def save_records(
        self,
        records: list[dict[str, Any]],
        snapshot_ref: dict[str, Any],
    ) -> list[str]:
        self.saved_batches.append(([dict(record) for record in records], dict(snapshot_ref)))
        for record in records:
            self.records[record["id"]] = dict(record)
        return [record["id"] for record in records]


class FakeFactRepository:
    def __init__(self, facts: list[dict[str, Any]]) -> None:
        self.facts = {fact["id"]: dict(fact) for fact in facts}

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [dict(self.facts[fact_id]) for fact_id in ids if fact_id in self.facts]

    def get_by_canonical_keys(self, canonical_keys: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def search_for_retrieval(self, **_: Any) -> list[dict[str, Any]]:
        return []

    def write_facts(self, records: list[dict[str, Any]], relations: list[dict[str, Any]], *, fact_snapshot_id: str) -> dict[str, Any]:
        return {}


class FakeSnapshotRepository:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, dict[str, Any]]] = []

    def publish_snapshot(
        self,
        layer: str,
        domain: str,
        snapshot_ref: dict[str, Any],
    ) -> str:
        self.published.append((layer, domain, dict(snapshot_ref)))
        return str(
            snapshot_ref.get("interpretation_snapshot_id") or snapshot_ref["fact_snapshot_id"]
        )


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.events: list[list[dict[str, Any]]] = []

    def append_events(self, events: list[dict[str, Any]]) -> list[str]:
        self.events.append([dict(event) for event in events])
        return [f"evt-{index}" for index, _ in enumerate(events, start=1)]


class FakeInterpretationPublicationRepository:
    def __init__(
        self,
        *,
        interpretation_repository: FakeInterpretationRepository,
        snapshot_repository: FakeSnapshotRepository,
        outbox_repository: FakeOutboxRepository,
        fail_after_records: bool = False,
    ) -> None:
        self.interpretation_repository = interpretation_repository
        self.snapshot_repository = snapshot_repository
        self.outbox_repository = outbox_repository
        self.fail_after_records = fail_after_records

    def publish_bundle(
        self,
        *,
        records: list[dict[str, Any]],
        domain: str,
        snapshot_ref: dict[str, Any],
        outbox_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        records_backup = {
            record_id: dict(record)
            for record_id, record in self.interpretation_repository.records.items()
        }
        snapshot_backup = list(self.snapshot_repository.published)
        outbox_backup = [[dict(event) for event in batch] for batch in self.outbox_repository.events]
        try:
            record_ids = self.interpretation_repository.save_records(records, snapshot_ref)
            if self.fail_after_records:
                raise RuntimeError("Simulated publish failure after interpretation save.")
            snapshot_id = self.snapshot_repository.publish_snapshot(
                "interpretation",
                domain,
                snapshot_ref,
            )
            outbox_event_ids = self.outbox_repository.append_events(outbox_events)
        except Exception:
            self.interpretation_repository.records = records_backup
            self.snapshot_repository.published = snapshot_backup
            self.outbox_repository.events = outbox_backup
            raise
        return {
            "record_ids": record_ids,
            "snapshot_id": snapshot_id,
            "outbox_event_ids": outbox_event_ids,
        }


class FakeInterpretationRenderingService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.replacements: list[dict[str, Any]] = []
        self.committed: list[dict[str, Any]] = []
        self.rolled_back: list[dict[str, Any]] = []

    def render_shared_page(self, *, record_id: str, scope_ref: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"record_id": record_id, "scope_ref": dict(scope_ref)})
        return {
            "record_id": record_id,
            "scope_ref": dict(scope_ref),
            "path": "wiki/shared/interpretations/market_trend/backend-japan-midlevel.md",
        }

    def replace_shared_page_atomically(
        self,
        *,
        record: dict[str, Any],
        scope_ref: dict[str, Any],
    ) -> dict[str, Any]:
        replacement = {
            "record_id": record["id"],
            "scope_ref": dict(scope_ref),
            "interpretation_snapshot_id": record["interpretation_snapshot_id"],
        }
        self.replacements.append(dict(replacement))
        return replacement

    def commit_shared_page_replacement(self, replacement: dict[str, Any] | None) -> None:
        if replacement is not None:
            self.committed.append(dict(replacement))

    def rollback_shared_page_replacement(self, replacement: dict[str, Any] | None) -> None:
        if replacement is not None:
            self.rolled_back.append(dict(replacement))


def test_publish_proposal_promotes_validated_market_trend_and_supersedes_prior_record() -> None:
    interpretation_repository = FakeInterpretationRepository(
        {
            "interp:proposal:1": _validated_record("interp:proposal:1"),
            "interp:published:older": {
                **_validated_record("interp:published:older"),
                "status": "published",
                "title": "Older trend",
                "claim": "Production AI hiring momentum is stabilizing.",
                "summary": "Demand is flattening for backend roles with production AI exposure.",
            },
        }
    )
    proposal_service = InterpretationProposalService(
        family_registry=InterpretationFamilyRegistry(),
        interpretation_repository=interpretation_repository,
        fact_repository=_fact_repository(),
    )
    snapshot_repository = FakeSnapshotRepository()
    outbox_repository = FakeOutboxRepository()
    publication_repository = FakeInterpretationPublicationRepository(
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
    )
    interpretation_rendering_service = FakeInterpretationRenderingService()
    publication_service = InterpretationPublicationService(
        proposal_service=proposal_service,
        interpretation_repository=interpretation_repository,
        publication_repository=publication_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
        interpretation_rendering_service=interpretation_rendering_service,
    )

    result = publication_service.publish_proposal(
        proposal_id="interp:proposal:1",
        scope_ref={"scope": "shared"},
    )

    assert result["ok"] is True
    assert result["status"] == "published"
    assert result["record"]["status"] == "published"
    assert result["interpretation_snapshot_id"].startswith(
        "interp_snap:recruiting:market_trend:backend-japan-midlevel:"
    )
    assert result["outbox_event_ids"] == ["evt-1"]
    assert interpretation_repository.records["interp:proposal:1"]["status"] == "published"
    assert interpretation_repository.records["interp:published:older"]["status"] == "superseded"
    assert snapshot_repository.published == [
        (
            "interpretation",
            "recruiting",
            {
                "fact_snapshot_id": "fact_snap:1",
                "interpretation_snapshot_id": result["interpretation_snapshot_id"],
            },
        )
    ]
    assert outbox_repository.events == [
        [
            {
                "event_type": "interpretation_snapshot_published",
                "aggregate_layer": "interpretation",
                "aggregate_id": result["interpretation_snapshot_id"],
                "idempotency_key": (
                    f"interpretation_snapshot_published:{result['interpretation_snapshot_id']}"
                ),
                "payload": {
                    "domain": "recruiting",
                    "interpretation_kind": "market_trend",
                    "fact_snapshot_id": "fact_snap:1",
                    "interpretation_snapshot_id": result["interpretation_snapshot_id"],
                    "interpretation_ids": ["interp:proposal:1"],
                    "source_event_id": "interp:proposal:1",
                    "scope": "shared",
                },
            }
        ]
    ]
    assert interpretation_rendering_service.replacements == [
        {
            "record_id": "interp:proposal:1",
            "scope_ref": {"scope": "shared"},
            "interpretation_snapshot_id": result["interpretation_snapshot_id"],
        }
    ]
    assert interpretation_rendering_service.committed == interpretation_rendering_service.replacements
    assert interpretation_rendering_service.rolled_back == []


def test_query_service_returns_only_published_records_by_default() -> None:
    interpretation_repository = FakeInterpretationRepository(
        {
            "interp:published:1": {
                **_validated_record("interp:published:1"),
                "status": "published",
                "summary": "Demand is trending upward.",
                "title": "Production LLM experience demand is rising",
                "interpretation_snapshot_id": "interp_snap:published:1",
            },
            "interp:validated:1": _validated_record("interp:validated:1"),
        }
    )
    service = InterpretationQueryService(
        interpretation_repository=interpretation_repository,
    )

    published = service.get_interpretation_record(
        record_id="interp:published:1",
        scope_ref={"scope": "shared"},
    )
    hidden = service.get_interpretation_record(
        record_id="interp:validated:1",
        scope_ref={"scope": "shared"},
    )
    matches = service.search_interpretations(
        domain="recruiting",
        question="LLM experience demand",
        scope_ref={"scope": "shared"},
    )

    assert published is not None
    assert published["status"] == "published"
    assert published["interpretation_snapshot_id"] == "interp_snap:published:1"
    assert hidden is None
    assert [record["id"] for record in matches] == ["interp:published:1"]
    assert matches[0]["interpretation_snapshot_id"] == "interp_snap:published:1"


def test_publish_proposal_marks_exact_duplicate_against_current_published_as_superseded() -> None:
    interpretation_repository = FakeInterpretationRepository(
        {
            "interp:proposal:duplicate": _validated_record("interp:proposal:duplicate"),
            "interp:published:1": {
                **_validated_record("interp:published:1"),
                "status": "published",
                "interpretation_snapshot_id": "interp_snap:published:1",
            },
        }
    )
    proposal_service = InterpretationProposalService(
        family_registry=InterpretationFamilyRegistry(),
        interpretation_repository=interpretation_repository,
        fact_repository=_fact_repository(),
    )
    snapshot_repository = FakeSnapshotRepository()
    outbox_repository = FakeOutboxRepository()
    publication_service = InterpretationPublicationService(
        proposal_service=proposal_service,
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
    )

    result = publication_service.publish_proposal(
        proposal_id="interp:proposal:duplicate",
        scope_ref={"scope": "shared"},
    )

    assert result["ok"] is False
    assert result["status"] == "superseded"
    assert result["duplicate_of"] == "interp:published:1"
    assert result["errors"][0]["code"] == "duplicate_published_interpretation"
    assert interpretation_repository.records["interp:proposal:duplicate"]["status"] == "superseded"
    assert interpretation_repository.records["interp:published:1"]["status"] == "published"
    assert snapshot_repository.published == []
    assert outbox_repository.events == []


def test_publish_proposal_blocks_near_duplicate_against_current_published_until_review() -> None:
    interpretation_repository = FakeInterpretationRepository(
        {
            "interp:proposal:near-duplicate": {
                **_validated_record("interp:proposal:near-duplicate"),
                "claim": "Production LLM experience demand keeps rising.",
                "summary": "Demand keeps trending upward.",
                "title": "Production LLM experience demand keeps rising",
            },
            "interp:published:1": {
                **_validated_record("interp:published:1"),
                "status": "published",
                "interpretation_snapshot_id": "interp_snap:published:1",
                "title": "Production LLM experience demand is rising",
            },
        }
    )
    proposal_service = InterpretationProposalService(
        family_registry=InterpretationFamilyRegistry(),
        interpretation_repository=interpretation_repository,
        fact_repository=_fact_repository(),
    )
    snapshot_repository = FakeSnapshotRepository()
    outbox_repository = FakeOutboxRepository()
    publication_service = InterpretationPublicationService(
        proposal_service=proposal_service,
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
    )

    result = publication_service.publish_proposal(
        proposal_id="interp:proposal:near-duplicate",
        scope_ref={"scope": "shared"},
    )

    assert result["ok"] is False
    assert result["status"] == "validated"
    assert result["duplicate_of"] == "interp:published:1"
    assert result["errors"][0]["code"] == "near_duplicate_published_interpretation"
    assert interpretation_repository.records["interp:proposal:near-duplicate"]["status"] == "validated"
    assert interpretation_repository.records["interp:published:1"]["status"] == "published"
    assert snapshot_repository.published == []
    assert outbox_repository.events == []


def test_publish_proposal_restores_render_and_canonical_state_when_publish_bundle_fails() -> None:
    interpretation_repository = FakeInterpretationRepository(
        {
            "interp:proposal:1": _validated_record("interp:proposal:1"),
            "interp:published:older": {
                **_validated_record("interp:published:older"),
                "status": "published",
                "interpretation_snapshot_id": "interp_snap:published:older",
                "title": "Older trend",
                "claim": "Production AI hiring momentum is stabilizing.",
                "summary": "Demand is flattening for backend roles with production AI exposure.",
            },
        }
    )
    proposal_service = InterpretationProposalService(
        family_registry=InterpretationFamilyRegistry(),
        interpretation_repository=interpretation_repository,
        fact_repository=_fact_repository(),
    )
    snapshot_repository = FakeSnapshotRepository()
    outbox_repository = FakeOutboxRepository()
    publication_repository = FakeInterpretationPublicationRepository(
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
        fail_after_records=True,
    )
    interpretation_rendering_service = FakeInterpretationRenderingService()
    publication_service = InterpretationPublicationService(
        proposal_service=proposal_service,
        interpretation_repository=interpretation_repository,
        publication_repository=publication_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
        interpretation_rendering_service=interpretation_rendering_service,
    )

    try:
        publication_service.publish_proposal(
            proposal_id="interp:proposal:1",
            scope_ref={"scope": "shared"},
        )
    except RuntimeError as exc:
        assert str(exc) == "Simulated publish failure after interpretation save."
    else:
        raise AssertionError("Expected publish_proposal to raise when the atomic bundle fails.")

    assert interpretation_repository.records["interp:proposal:1"]["status"] == "validated"
    assert interpretation_repository.records["interp:published:older"]["status"] == "published"
    assert snapshot_repository.published == []
    assert outbox_repository.events == []
    assert interpretation_rendering_service.committed == []
    assert len(interpretation_rendering_service.rolled_back) == 1


def test_publish_proposal_restores_prior_rendered_page_when_atomic_publish_fails(
    tmp_path: Path,
) -> None:
    interpretation_repository = FakeInterpretationRepository(
        {
            "interp:proposal:1": _validated_record("interp:proposal:1"),
            "interp:published:older": {
                **_validated_record("interp:published:older"),
                "status": "published",
                "interpretation_snapshot_id": "interp_snap:published:older",
                "title": "Older trend",
                "claim": "Production AI hiring momentum is stabilizing.",
                "summary": "Demand is flattening for backend roles with production AI exposure.",
            },
        }
    )
    rendering_repository = FileSystemRenderingRepository(tmp_path)
    page_path = tmp_path / "wiki" / "shared" / "interpretations" / "market_trend" / "backend-japan-midlevel.md"
    rendering_repository.write_artifact(
        {
            "domain": "recruiting",
            "layer": "interpretation",
            "record_id": "interp:published:older",
            "path": "wiki/shared/interpretations/market_trend/backend-japan-midlevel.md",
            "title": "Older page",
            "body_markdown": "old published body",
            "scope_ref": {"scope": "shared"},
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:1",
                "interpretation_snapshot_id": "interp_snap:published:older",
            },
        }
    )
    proposal_service = InterpretationProposalService(
        family_registry=InterpretationFamilyRegistry(),
        interpretation_repository=interpretation_repository,
        fact_repository=_fact_repository(),
    )
    snapshot_repository = FakeSnapshotRepository()
    outbox_repository = FakeOutboxRepository()
    publication_repository = FakeInterpretationPublicationRepository(
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
        fail_after_records=True,
    )
    interpretation_rendering_service = InterpretationRenderingService(
        interpretation_repository=interpretation_repository,
        rendering_repository=rendering_repository,
    )
    publication_service = InterpretationPublicationService(
        proposal_service=proposal_service,
        interpretation_repository=interpretation_repository,
        publication_repository=publication_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
        interpretation_rendering_service=interpretation_rendering_service,
    )

    try:
        publication_service.publish_proposal(
            proposal_id="interp:proposal:1",
            scope_ref={"scope": "shared"},
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected publish_proposal to raise when the atomic bundle fails.")

    assert page_path.read_text(encoding="utf-8") == "old published body"


def _validated_record(record_id: str) -> dict[str, Any]:
    return {
        "id": record_id,
        "layer": "interpretation",
        "domain": "recruiting",
        "family": "market_trend",
        "kind": "market_trend",
        "subject_type": "market_segment",
        "subject_id": "backend-japan-midlevel",
        "scope_ref": {"scope": "shared"},
        "schema_version": "interpretation.v2",
        "status": "validated",
        "confidence": 0.82,
        "fact_snapshot_id": "fact_snap:1",
        "computed_at": "2026-04-17T10:00:00Z",
        "expires_at": "2026-04-18T10:00:00Z",
        "claim": "Production LLM experience preference is increasing.",
        "summary": "Demand is trending upward.",
        "body": {"signals": ["llm"], "observations": [], "counterpoints": []},
        "evidence": [{"fact_id": "fact:job:1", "weight": 0.7, "role": "primary"}],
        "provenance": {"generated_by": {"kind": "llm"}},
        "render_hints": {"page_family": "market_trend"},
    }


def _fact_repository() -> FakeFactRepository:
    return FakeFactRepository(
        [
            {
                "id": "fact:job:1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job:1",
                "attributes": {"title": "Backend Engineer"},
                "scope": "shared",
                "schema_version": "fact.v1",
                "provenance": {"source_ids": ["job:1"]},
            }
        ]
    )
