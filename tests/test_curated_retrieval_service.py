from __future__ import annotations

from typing import Any

from wiki_mcp.services.personal_query import PersonalQueryOrchestrator
from wiki_mcp.services.retrieval import CuratedRetrievalService


class StubFactRepository:
    def __init__(
        self,
        *,
        by_id: dict[str, dict[str, Any]] | None = None,
        search_results: list[dict[str, Any]] | None = None,
    ) -> None:
        self.by_id = by_id or {}
        self.search_results = search_results or []
        self.search_calls: list[dict[str, Any]] = []

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [self.by_id[record_id] for record_id in ids if record_id in self.by_id]

    def search_for_retrieval(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.search_calls.append(dict(kwargs))
        return list(self.search_results)


class StubInterpretationRepository:
    def __init__(
        self,
        *,
        by_id: dict[str, dict[str, Any]] | None = None,
        search_results: list[dict[str, Any]] | None = None,
    ) -> None:
        self.by_id = by_id or {}
        self.search_results = search_results or []
        self.search_calls: list[dict[str, Any]] = []

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [self.by_id[record_id] for record_id in ids if record_id in self.by_id]

    def search_for_retrieval(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.search_calls.append(dict(kwargs))
        return list(self.search_results)


class StubPersonalRepository:
    def __init__(self, *, search_results: list[dict[str, Any]] | None = None) -> None:
        self.search_results = search_results or []
        self.search_calls: list[dict[str, Any]] = []

    def search_for_retrieval(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.search_calls.append(dict(kwargs))
        return list(self.search_results)


def _scope_ref() -> dict[str, str]:
    return {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"}


def _interpretation(
    record_id: str,
    *,
    evidence: list[dict[str, Any]] | None = None,
    status: str = "published",
) -> dict[str, Any]:
    return {
        "id": record_id,
        "domain": "recruiting",
        "family": "market_trend",
        "kind": "trend",
        "subject_type": "market_segment",
        "subject_id": "backend-japan-midlevel",
        "status": status,
        "confidence": 0.82,
        "summary": "Shared summary",
        "fact_snapshot_id": "fact_snap:1",
        "body": {"summary": "Shared summary"},
        "evidence": evidence or [],
    }


def _fact(record_id: str, title: str) -> dict[str, Any]:
    return {
        "id": record_id,
        "domain": "recruiting",
        "entity_type": "job_posting",
        "canonical_key": f"job:{record_id}",
        "scope": "shared",
        "fact_snapshot_id": "fact_snap:1",
        "attributes": {"title": title},
    }


def test_curated_retrieval_expands_personal_anchors_then_interpretation_evidence() -> None:
    personal_repository = StubPersonalRepository(
        search_results=[
            {
                "id": "personal:1",
                "domain": "recruiting",
                "kind": "plan",
                "title": "My backend plan",
                "summary": "Anchored to shared context",
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:1",
                    "interpretation_snapshot_id": "interp_snap:1",
                    "profile_version": "profile:v1",
                },
                "anchors": [
                    {"layer": "interpretation", "id": "interp:1"},
                    {"layer": "fact", "id": "fact:personal-anchor"},
                ],
            }
        ]
    )
    interpretation_repository = StubInterpretationRepository(
        by_id={
            "interp:1": _interpretation(
                "interp:1",
                evidence=[
                    {"fact_id": "fact:evidence:2", "weight": 0.9},
                    {"fact_id": "fact:evidence:1", "weight": 0.4},
                ],
            )
        },
        search_results=[
            _interpretation("interp:search"),
        ],
    )
    fact_repository = StubFactRepository(
        by_id={
            "fact:evidence:2": _fact("fact:evidence:2", "Second evidence"),
            "fact:evidence:1": _fact("fact:evidence:1", "First evidence"),
            "fact:personal-anchor": _fact("fact:personal-anchor", "Anchored fact"),
        },
        search_results=[],
    )

    service = CuratedRetrievalService(
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        personal_repository=personal_repository,
        layer_result_limit=4,
        evidence_fact_limit=2,
    )

    result = service.retrieve_for_query(
        domain="recruiting",
        question="What matters for backend roles?",
        scope_ref=_scope_ref(),
        profile_context={
            "user_id": "user-1",
            "tenant_id": "tenant-1",
            "domain": "recruiting",
            "profile_version": "profile:v1",
            "goals": ["find backend roles"],
            "preferences": {"location": "jp"},
            "attributes": {"level": "mid"},
        },
    )

    assert result["personal_ids"] == ["personal:1"]
    assert result["interpretation_ids"] == ["interp:1"]
    assert result["fact_ids"] == [
        "fact:evidence:2",
        "fact:evidence:1",
        "fact:personal-anchor",
    ]
    assert interpretation_repository.search_calls == []
    assert fact_repository.search_calls == []
    assert result["interpretation_explanations"][0]["match_type"] == "personal_anchor_expansion"
    assert result["fact_explanations"][0]["match_type"] == "interpretation_evidence"
    assert result["retrieval_metadata"] == {
        "mode": "curated",
        "layer_order": ["personal", "interpretation", "fact"],
        "backend": "repository",
        "personal_anchor_status": "present",
        "interpretation_source": "personal_anchors",
        "fact_source": "interpretation_evidence",
        "evidence_fact_limit": 2,
    }


def test_curated_retrieval_falls_back_to_interpretation_search_when_personal_anchors_absent() -> None:
    personal_repository = StubPersonalRepository(
        search_results=[
            {
                "id": "personal:1",
                "domain": "recruiting",
                "kind": "note",
                "title": "General note",
                "summary": "No explicit anchors yet",
                "snapshot_ref": {"fact_snapshot_id": "fact_snap:1"},
            }
        ]
    )
    interpretation_repository = StubInterpretationRepository(
        search_results=[
            _interpretation(
                "interp:search",
                evidence=[{"fact_id": "fact:search", "weight": 0.7}],
            )
        ]
    )
    fact_repository = StubFactRepository(
        by_id={"fact:search": _fact("fact:search", "Matched evidence")}
    )

    service = CuratedRetrievalService(
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        personal_repository=personal_repository,
    )

    result = service.retrieve_for_query(
        domain="recruiting",
        question="What trends should I care about?",
        scope_ref=_scope_ref(),
    )

    assert result["interpretation_ids"] == ["interp:search"]
    assert result["fact_ids"] == ["fact:search"]
    assert interpretation_repository.search_calls[0]["query_text"] == "What trends should I care about?"
    assert result["retrieval_metadata"]["personal_anchor_status"] == "absent"
    assert result["retrieval_metadata"]["interpretation_source"] == "search_fallback"
    assert result["retrieval_metadata"]["fact_source"] == "interpretation_evidence"


def test_curated_retrieval_keeps_body_anchor_compatibility_when_metadata_absent() -> None:
    personal_repository = StubPersonalRepository(
        search_results=[
            {
                "id": "personal:legacy:1",
                "domain": "recruiting",
                "kind": "note",
                "title": "Legacy note",
                "summary": "Still stores anchors in body metadata",
                "snapshot_ref": {"fact_snapshot_id": "fact_snap:1"},
                "body": {
                    "anchors": [
                        {"layer": "interpretation", "id": "interp:legacy"},
                        {"layer": "fact", "id": "fact:legacy"},
                    ]
                },
            }
        ]
    )
    interpretation_repository = StubInterpretationRepository(
        by_id={"interp:legacy": _interpretation("interp:legacy", evidence=[])},
    )
    fact_repository = StubFactRepository(
        by_id={"fact:legacy": _fact("fact:legacy", "Legacy anchored fact")},
        search_results=[],
    )

    service = CuratedRetrievalService(
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        personal_repository=personal_repository,
    )

    result = service.retrieve_for_query(
        domain="recruiting",
        question="Legacy anchored answer",
        scope_ref=_scope_ref(),
    )

    assert result["interpretation_ids"] == ["interp:legacy"]
    assert result["fact_ids"] == ["fact:legacy"]
    assert result["retrieval_metadata"]["personal_anchor_status"] == "present"


def test_curated_retrieval_uses_fact_search_fallback_when_no_evidence_exists() -> None:
    interpretation_repository = StubInterpretationRepository(
        search_results=[_interpretation("interp:no-evidence", evidence=[])]
    )
    fact_repository = StubFactRepository(
        search_results=[_fact("fact:fallback", "Fallback match")]
    )
    service = CuratedRetrievalService(
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        personal_repository=StubPersonalRepository(search_results=[]),
    )

    result = service.retrieve_for_query(
        domain="recruiting",
        question="Need evidence fallback",
        scope_ref=_scope_ref(),
    )

    assert result["interpretation_ids"] == ["interp:no-evidence"]
    assert result["fact_ids"] == ["fact:fallback"]
    assert fact_repository.search_calls[0]["query_text"] == "Need evidence fallback"
    assert result["retrieval_metadata"]["fact_source"] == "search_fallback"
    assert result["fact_explanations"][0]["match_type"] == "curated_repository_search"


def test_personal_query_bundle_carries_retrieval_metadata() -> None:
    service = CuratedRetrievalService(
        fact_repository=StubFactRepository(search_results=[]),
        interpretation_repository=StubInterpretationRepository(search_results=[]),
        personal_repository=StubPersonalRepository(search_results=[]),
    )
    orchestrator = PersonalQueryOrchestrator(retrieval_service=service)

    retrieval, bundle = orchestrator.build_query_bundle(
        domain="recruiting",
        question="Question",
        scope_ref=_scope_ref(),
    )

    assert bundle["retrieval_metadata"] == retrieval["retrieval_metadata"]
