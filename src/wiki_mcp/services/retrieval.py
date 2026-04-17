from __future__ import annotations

from typing import Any

from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.retrieval_fact_summary import RetrievalFactSummary
from wiki_mcp.schemas.retrieval_interpretation_summary import (
    RetrievalInterpretationSummary,
)
from wiki_mcp.schemas.retrieval_match_explanation import RetrievalMatchExplanation
from wiki_mcp.schemas.retrieval_personal_summary import RetrievalPersonalSummary
from wiki_mcp.schemas.retrieval_result import RetrievalResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.services.interfaces.repositories import (
    FactRepository,
    InterpretationRepository,
    PersonalRepository,
)


class CuratedRetrievalService:
    """Repo-backed curated retrieval across Personal, Interpretation, and Fact.

    This service intentionally avoids legacy page-read-first behavior. It is a
    thin implementation of the current docs-defined default retrieval mode:
    `Personal -> Interpretation -> Fact`.
    """

    layer_order = ("personal", "interpretation", "fact")

    def __init__(
        self,
        *,
        fact_repository: FactRepository | None = None,
        interpretation_repository: InterpretationRepository | None = None,
        personal_repository: PersonalRepository | None = None,
        layer_result_limit: int = 5,
    ) -> None:
        self.fact_repository = fact_repository
        self.interpretation_repository = interpretation_repository
        self.personal_repository = personal_repository
        self.layer_result_limit = layer_result_limit

    def retrieve_for_query(
        self,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext | None = None,
    ) -> RetrievalResult:
        normalized_question = question.strip()
        query_tokens = self._tokenize(question)
        if not normalized_question:
            return self._empty_result()

        personal_records = self._search_personal(
            domain=domain,
            question=normalized_question,
            query_tokens=query_tokens,
            scope_ref=scope_ref,
        )
        interpretation_records = self._search_interpretation(
            domain=domain,
            question=normalized_question,
            query_tokens=query_tokens,
            scope_ref=scope_ref,
        )
        fact_records = self._search_fact(
            domain=domain,
            question=normalized_question,
            query_tokens=query_tokens,
            scope_ref=scope_ref,
        )

        result: RetrievalResult = {
            "personal_ids": [record["id"] for record in personal_records],
            "interpretation_ids": [record["id"] for record in interpretation_records],
            "fact_ids": [record["id"] for record in fact_records],
            "personal_records": [self._map_personal_record(record) for record in personal_records],
            "interpretation_records": [
                self._map_interpretation_record(record)
                for record in interpretation_records
            ],
            "fact_records": [self._map_fact_record(record) for record in fact_records],
            "personal_explanations": self._build_explanations(
                layer="personal",
                records=personal_records,
                query_tokens=query_tokens,
                profile_context=profile_context,
            ),
            "interpretation_explanations": self._build_explanations(
                layer="interpretation",
                records=interpretation_records,
                query_tokens=query_tokens,
                profile_context=None,
            ),
            "fact_explanations": self._build_explanations(
                layer="fact",
                records=fact_records,
                query_tokens=query_tokens,
                profile_context=None,
            ),
        }

        snapshot_ref = self._merge_snapshot_ref(
            personal_records=personal_records,
            interpretation_records=interpretation_records,
            fact_records=fact_records,
        )
        if snapshot_ref is not None:
            result["snapshot_ref"] = snapshot_ref

        return result

    def _empty_result(self) -> RetrievalResult:
        return {
            "personal_ids": [],
            "interpretation_ids": [],
            "fact_ids": [],
            "personal_records": [],
            "interpretation_records": [],
            "fact_records": [],
            "personal_explanations": [],
            "interpretation_explanations": [],
            "fact_explanations": [],
        }

    def _search_personal(
        self,
        *,
        domain: str,
        question: str,
        query_tokens: list[str],
        scope_ref: ScopeRef,
    ) -> list[dict[str, Any]]:
        if self.personal_repository is None:
            return []
        return list(
            self.personal_repository.search_for_retrieval(
                domain=domain,
                scope_ref=scope_ref,
                query_text=question,
                query_tokens=query_tokens,
                limit=self.layer_result_limit,
            )
        )

    def _search_interpretation(
        self,
        *,
        domain: str,
        question: str,
        query_tokens: list[str],
        scope_ref: ScopeRef,
    ) -> list[dict[str, Any]]:
        if self.interpretation_repository is None:
            return []
        return list(
            self.interpretation_repository.search_for_retrieval(
                domain=domain,
                scope_ref=scope_ref,
                query_text=question,
                query_tokens=query_tokens,
                limit=self.layer_result_limit,
            )
        )

    def _search_fact(
        self,
        *,
        domain: str,
        question: str,
        query_tokens: list[str],
        scope_ref: ScopeRef,
    ) -> list[dict[str, Any]]:
        if self.fact_repository is None:
            return []
        return list(
            self.fact_repository.search_for_retrieval(
                domain=domain,
                scope_ref=scope_ref,
                query_text=question,
                query_tokens=query_tokens,
                limit=self.layer_result_limit,
            )
        )

    def _map_personal_record(self, record: dict[str, Any]) -> RetrievalPersonalSummary:
        return {
            "id": record["id"],
            "domain": record["domain"],
            "kind": record["kind"],
            "title": record["title"],
            "summary": record["summary"],
            "snapshot_ref": record["snapshot_ref"],
        }

    def _map_interpretation_record(
        self,
        record: dict[str, Any],
    ) -> RetrievalInterpretationSummary:
        body = record.get("body", {})
        summary = None
        if isinstance(body, dict):
            raw_summary = body.get("summary")
            if isinstance(raw_summary, str) and raw_summary.strip():
                summary = raw_summary.strip()
        result: RetrievalInterpretationSummary = {
            "id": record["id"],
            "domain": record["domain"],
            "kind": record["kind"],
            "subject_type": record["subject_type"],
            "subject_id": record["subject_id"],
            "status": record["status"],
            "confidence": record["confidence"],
        }
        if summary:
            result["summary"] = summary
        return result

    def _map_fact_record(self, record: dict[str, Any]) -> RetrievalFactSummary:
        attributes = record.get("attributes", {})
        title = None
        if isinstance(attributes, dict):
            for key in ("title", "name", "label", "summary"):
                value = attributes.get(key)
                if isinstance(value, str) and value.strip():
                    title = value.strip()
                    break

        result: RetrievalFactSummary = {
            "id": record["id"],
            "domain": record["domain"],
            "entity_type": record["entity_type"],
            "canonical_key": record["canonical_key"],
            "scope": record["scope"],
        }
        if title:
            result["title"] = title
        if record.get("fact_snapshot_id"):
            result["fact_snapshot_id"] = record["fact_snapshot_id"]
        return result

    def _build_explanations(
        self,
        *,
        layer: str,
        records: list[dict[str, Any]],
        query_tokens: list[str],
        profile_context: ProfileContext | None,
    ) -> list[RetrievalMatchExplanation]:
        explanations: list[RetrievalMatchExplanation] = []
        for index, record in enumerate(records, start=1):
            matched_fields = self._matched_fields(record, query_tokens)
            explanations.append(
                {
                    "layer": layer,  # type: ignore[typeddict-item]
                    "record_id": record["id"],
                    "rank": index,
                    "score": max(len(matched_fields), 1),
                    "match_type": "curated_repository_search",
                    "matched_fields": matched_fields or ["repository_search"],
                    "matched_token_count": len(query_tokens),
                    "profile_boost_applied": profile_context is not None and layer == "personal",
                    "has_rendered_page": False,
                }
            )
        return explanations

    def _matched_fields(
        self,
        record: dict[str, Any],
        query_tokens: list[str],
    ) -> list[str]:
        candidates: list[tuple[str, str]] = []
        for key in ("title", "summary", "kind", "entity_type", "canonical_key", "subject_id"):
            value = record.get(key)
            if isinstance(value, str):
                candidates.append((key, value.lower()))

        attributes = record.get("attributes")
        if isinstance(attributes, dict):
            for key in ("title", "name", "label", "summary", "description"):
                value = attributes.get(key)
                if isinstance(value, str):
                    candidates.append((f"attributes.{key}", value.lower()))

        matched: list[str] = []
        for field, haystack in candidates:
            if any(token in haystack for token in query_tokens):
                matched.append(field)
        return matched

    def _merge_snapshot_ref(
        self,
        *,
        personal_records: list[dict[str, Any]],
        interpretation_records: list[dict[str, Any]],
        fact_records: list[dict[str, Any]],
    ) -> SnapshotRef | None:
        merged: SnapshotRef = {}

        for record in personal_records:
            snapshot_ref = record.get("snapshot_ref")
            if isinstance(snapshot_ref, dict):
                if snapshot_ref.get("fact_snapshot_id") and not merged.get("fact_snapshot_id"):
                    merged["fact_snapshot_id"] = snapshot_ref["fact_snapshot_id"]
                if snapshot_ref.get("interpretation_snapshot_id") and not merged.get(
                    "interpretation_snapshot_id"
                ):
                    merged["interpretation_snapshot_id"] = snapshot_ref[
                        "interpretation_snapshot_id"
                    ]
                if snapshot_ref.get("profile_version") and not merged.get("profile_version"):
                    merged["profile_version"] = snapshot_ref["profile_version"]

        for record in interpretation_records:
            fact_snapshot_id = record.get("fact_snapshot_id")
            if fact_snapshot_id and not merged.get("fact_snapshot_id"):
                merged["fact_snapshot_id"] = fact_snapshot_id

        for record in fact_records:
            fact_snapshot_id = record.get("fact_snapshot_id")
            if fact_snapshot_id and not merged.get("fact_snapshot_id"):
                merged["fact_snapshot_id"] = fact_snapshot_id

        return merged or None

    def _tokenize(self, question: str) -> list[str]:
        return [token for token in question.lower().split() if token]
