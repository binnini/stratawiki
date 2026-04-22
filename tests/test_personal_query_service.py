from __future__ import annotations

from pathlib import Path
from typing import Any

from wiki_mcp.adapters.llm import DeterministicLLMGateway
from wiki_mcp.prompts import PromptCatalog
from wiki_mcp.services.personal_query import (
    PersonalKnowledgeQueryService,
    PersonalQueryOrchestrator,
)
from wiki_mcp.storage.filesystem import FileSystemRenderingRepository


class StubRetrievalService:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def retrieve_for_query(
        self,
        domain: str,
        question: str,
        scope_ref: dict[str, str],
        profile_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "domain": domain,
                "question": question,
                "scope_ref": dict(scope_ref),
                "profile_context": dict(profile_context or {}),
            }
        )
        return dict(self.result)


class StubPersonalRepository:
    def __init__(self) -> None:
        self.saved_records: list[dict[str, Any]] = []

    def save_record(self, record: dict[str, Any]) -> str:
        self.saved_records.append(dict(record))
        return str(record["id"])


def _scope_ref() -> dict[str, str]:
    return {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"}


def _profile_context() -> dict[str, Any]:
    return {
        "user_id": "user-1",
        "tenant_id": "tenant-1",
        "domain": "recruiting",
        "profile_version": "profile:v1",
        "goals": ["find backend roles"],
        "preferences": {"location": "jp"},
        "attributes": {"level": "mid"},
    }


def _retrieval_result() -> dict[str, Any]:
    return {
        "personal_ids": ["personal:existing:1"],
        "interpretation_ids": ["interp:1"],
        "fact_ids": ["fact:1"],
        "personal_records": [
            {
                "id": "personal:existing:1",
                "kind": "plan",
                "title": "Existing plan",
                "summary": "Prior saved plan",
                "path": "wiki/users/user-1/plans/existing-plan.md",
            }
        ],
        "interpretation_records": [
            {
                "id": "interp:1",
                "kind": "trend",
                "subject_id": "backend-japan-midlevel",
                "title": "Demand is rising",
                "summary": "Demand is rising for backend roles with production AI exposure.",
                "status": "published",
                "confidence": 0.82,
            }
        ],
        "fact_records": [
            {
                "id": "fact:1",
                "title": "Backend Engineer",
                "canonical_key": "job:1",
            }
        ],
        "personal_explanations": [
            {
                "record_id": "personal:existing:1",
                "rank": 1,
                "score": 9,
                "matched_token_count": 3,
                "matched_fields": ["title"],
                "has_rendered_page": True,
                "match_type": "personal_search",
            }
        ],
        "interpretation_explanations": [
            {
                "record_id": "interp:1",
                "rank": 1,
                "score": 8,
                "matched_token_count": 2,
                "matched_fields": ["summary"],
                "has_rendered_page": False,
                "match_type": "personal_anchor_expansion",
            }
        ],
        "fact_explanations": [
            {
                "record_id": "fact:1",
                "rank": 1,
                "score": 7,
                "matched_token_count": 2,
                "matched_fields": ["title"],
                "has_rendered_page": False,
                "match_type": "interpretation_evidence",
            }
        ],
        "retrieval_metadata": {
            "mode": "curated",
            "layer_order": ["personal", "interpretation", "fact"],
            "backend": "repository",
            "personal_search_policy": "metadata_first_markdown_support",
            "personal_support_source": "none",
            "personal_anchor_status": "present",
            "interpretation_source": "personal_anchors",
            "fact_source": "interpretation_evidence",
            "evidence_fact_limit": 3,
            "graph_behavior": "support_only",
        },
        "snapshot_ref": {
            "fact_snapshot_id": "fact_snap:1",
            "interpretation_snapshot_id": "interp_snap:1",
            "profile_version": "profile:v1",
        },
    }


def test_query_personal_knowledge_returns_answer_with_snapshot_bound_provenance() -> None:
    retrieval_service = StubRetrievalService(_retrieval_result())
    orchestrator = PersonalQueryOrchestrator(retrieval_service=retrieval_service)
    gateway = DeterministicLLMGateway(
        provider="mock",
        model="mock-model-v1",
        default_text="## Strategy\n\nFocus on backend roles with production AI exposure.",
    )
    service = PersonalKnowledgeQueryService(
        orchestrator=orchestrator,
        llm_gateway=gateway,
    )

    answer = service.query_personal_knowledge(
        domain="recruiting",
        question="What should I focus on next?",
        scope_ref=_scope_ref(),
        profile_context=_profile_context(),
        model_profile="deep_synthesis",
        save=False,
    )

    assert answer["answer_type"] == "personal_query_answer"
    assert answer["generation_strategy"] == "curated_retrieval_llm_v1"
    assert answer["personal_records_used"] == ["personal:existing:1"]
    assert answer["interpretation_records_used"] == ["interp:1"]
    assert answer["fact_records_used"] == ["fact:1"]
    assert answer["provenance"] == {
        "fact_snapshot": "fact_snap:1",
        "interpretation_snapshot": "interp_snap:1",
        "profile_version": "profile:v1",
        "model_profile": "deep_synthesis",
        "prompt_id": "personal.query.answer",
        "prompt_version": "personal.query.answer.v1",
        "provider": "mock",
        "model": "mock-model-v1",
    }
    assert answer["citations"][0] == {
        "layer": "personal",
        "record_id": "personal:existing:1",
        "title": "Existing plan",
        "path": "wiki/users/user-1/plans/existing-plan.md",
    }
    assert answer["input_bundle"]["snapshot_ref"]["fact_snapshot_id"] == "fact_snap:1"


def test_query_personal_knowledge_save_persists_metadata_and_markdown_body(
    tmp_path: Path,
) -> None:
    retrieval_service = StubRetrievalService(_retrieval_result())
    orchestrator = PersonalQueryOrchestrator(retrieval_service=retrieval_service)
    personal_repository = StubPersonalRepository()
    rendering_repository = FileSystemRenderingRepository(tmp_path)
    gateway = DeterministicLLMGateway(
        provider="mock",
        model="mock-model-v1",
        default_text="## Strategy\n\nPrioritize roles that mention production AI systems.",
    )
    service = PersonalKnowledgeQueryService(
        orchestrator=orchestrator,
        llm_gateway=gateway,
        personal_repository=personal_repository,
        rendering_repository=rendering_repository,
    )

    answer = service.query_personal_knowledge(
        domain="recruiting",
        question="What should I focus on next?",
        scope_ref=_scope_ref(),
        profile_context=_profile_context(),
        model_profile="balanced_default",
        save=True,
    )

    assert len(personal_repository.saved_records) == 1
    saved_record = personal_repository.saved_records[0]
    assert saved_record["kind"] == "query_answer"
    assert saved_record["scope_ref"] == _scope_ref()
    assert saved_record["snapshot_ref"] == {
        "fact_snapshot_id": "fact_snap:1",
        "interpretation_snapshot_id": "interp_snap:1",
        "profile_version": "profile:v1",
    }
    assert saved_record["profile_version"] == "profile:v1"
    assert saved_record["subspace"] == "wiki"
    assert saved_record["asset_refs"] == []
    assert saved_record["version"] == 1
    assert saved_record["path"].startswith("wiki/users/user-1/answers/")
    assert saved_record["anchors"] == [
        {"layer": "interpretation", "id": "interp:1"},
        {"layer": "fact", "id": "fact:1"},
    ]

    persisted_path = tmp_path / saved_record["path"]
    assert persisted_path.exists()
    persisted_body = persisted_path.read_text(encoding="utf-8")
    assert persisted_body == answer["answer_markdown"] + "\n"


def test_query_personal_knowledge_supports_korean_prompt_templates() -> None:
    retrieval_service = StubRetrievalService(_retrieval_result())
    orchestrator = PersonalQueryOrchestrator(retrieval_service=retrieval_service)
    captured_request: dict[str, Any] = {}

    def capture_request(request: dict[str, Any]) -> str:
        captured_request["request"] = request
        return "## 답변\n\n테스트"

    gateway = DeterministicLLMGateway(
        provider="mock",
        model="mock-model-v1",
        text_factory=capture_request,
    )
    service = PersonalKnowledgeQueryService(
        orchestrator=orchestrator,
        llm_gateway=gateway,
        prompt_catalog=PromptCatalog(language="ko"),
    )

    answer = service.query_personal_knowledge(
        domain="recruiting",
        question="무엇에 집중해야 하나요?",
        scope_ref=_scope_ref(),
        profile_context=_profile_context(),
        model_profile="balanced_default",
        save=False,
    )

    request = captured_request["request"]
    assert "사용자 범위 Personal 답변" in request["messages"][0]["content"]
    assert "질문:" in request["messages"][1]["content"]
    assert answer["provenance"]["prompt_version"] == "personal.query.answer.v1.ko"
