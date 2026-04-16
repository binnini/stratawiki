from __future__ import annotations

import re
from typing import Any, cast

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.personal_record import PersonalRecord
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
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
from wiki_mcp.services.interfaces.page_reads import PageReadService


class DefaultRetrievalService:
    """Minimal structured retrieval across rendered Personal, Interpretation, and Fact pages."""

    layer_order = ("personal", "interpretation", "fact")

    def __init__(
        self,
        *,
        page_read_service: PageReadService,
        fact_repository: FactRepository | None = None,
        interpretation_repository: InterpretationRepository | None = None,
        personal_repository: PersonalRepository | None = None,
        page_scan_limit: int = 50,
        layer_result_limit: int = 5,
    ) -> None:
        self.page_read_service = page_read_service
        self.fact_repository = fact_repository
        self.interpretation_repository = interpretation_repository
        self.personal_repository = personal_repository
        self.page_scan_limit = page_scan_limit
        self.layer_result_limit = layer_result_limit

    def retrieve_for_query(
        self,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext | None = None,
    ) -> RetrievalResult:
        normalized_question = self._normalize(question)
        if not normalized_question:
            return {
                "personal_ids": [],
                "interpretation_ids": [],
                "fact_ids": [],
                "personal_pages": [],
                "interpretation_pages": [],
                "fact_pages": [],
                "personal_explanations": [],
                "interpretation_explanations": [],
                "fact_explanations": [],
            }

        query_tokens = self._tokenize(question)
        structured_lookup = self._looks_structured(question)
        matches_by_layer: dict[str, list[RenderedPageSummary]] = {}
        explanations_by_layer: dict[str, list[RetrievalMatchExplanation]] = {}

        for layer in self.layer_order:
            pages = self.page_read_service.list_pages(
                domain=domain,
                scope_ref=self._scope_for_layer(layer, scope_ref),
                layer=layer,
                limit=self.page_scan_limit,
            )
            matched_candidates = self._match_pages(
                pages,
                layer=layer,
                normalized_question=normalized_question,
                query_tokens=query_tokens,
                structured_lookup=structured_lookup,
                profile_context=profile_context,
            )[: self.layer_result_limit]
            matches_by_layer[layer] = [page for page, _ in matched_candidates]
            explanations_by_layer[layer] = [explanation for _, explanation in matched_candidates]

        result: RetrievalResult = {
            "personal_ids": [page["record_id"] for page in matches_by_layer["personal"]],
            "interpretation_ids": [
                page["record_id"] for page in matches_by_layer["interpretation"]
            ],
            "fact_ids": [page["record_id"] for page in matches_by_layer["fact"]],
            "personal_pages": matches_by_layer["personal"],
            "interpretation_pages": matches_by_layer["interpretation"],
            "fact_pages": matches_by_layer["fact"],
            "personal_explanations": explanations_by_layer["personal"],
            "interpretation_explanations": explanations_by_layer["interpretation"],
            "fact_explanations": explanations_by_layer["fact"],
        }
        hydrated_records = self._hydrate_records(matches_by_layer, requested_scope=scope_ref)
        result.update(hydrated_records)

        snapshot_ref = self._merge_snapshot_ref(matches_by_layer)
        if snapshot_ref is not None:
            result["snapshot_ref"] = snapshot_ref

        return result

    def _hydrate_records(
        self,
        matches_by_layer: dict[str, list[RenderedPageSummary]],
        *,
        requested_scope: ScopeRef,
    ) -> RetrievalResult:
        hydrated: dict[str, Any] = {}

        personal_ids = [page["record_id"] for page in matches_by_layer["personal"]]
        if personal_ids and self.personal_repository is not None:
            hydrated["personal_records"] = self._ordered_records(
                personal_ids,
                self._map_personal_records(
                    self.personal_repository.get_by_ids(personal_ids, requested_scope)
                ),
            )

        interpretation_ids = [
            page["record_id"] for page in matches_by_layer["interpretation"]
        ]
        if interpretation_ids and self.interpretation_repository is not None:
            hydrated["interpretation_records"] = self._ordered_records(
                interpretation_ids,
                self._map_interpretation_records(
                    self.interpretation_repository.get_by_ids(
                        interpretation_ids,
                        self._scope_for_layer("interpretation", requested_scope),
                    )
                ),
            )

        fact_ids = [page["record_id"] for page in matches_by_layer["fact"]]
        if fact_ids and self.fact_repository is not None:
            hydrated["fact_records"] = self._ordered_records(
                fact_ids,
                self._map_fact_records(
                    self.fact_repository.get_by_ids(
                        fact_ids,
                        self._scope_for_layer("fact", requested_scope),
                    )
                ),
            )

        return cast(RetrievalResult, hydrated)

    def _ordered_records(
        self,
        expected_ids: list[str],
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        records_by_id = {record["id"]: record for record in records}
        return [records_by_id[record_id] for record_id in expected_ids if record_id in records_by_id]

    def _map_personal_records(
        self,
        records: list[PersonalRecord],
    ) -> list[RetrievalPersonalSummary]:
        return [
            {
                "id": record["id"],
                "domain": record["domain"],
                "kind": record["kind"],
                "title": record["title"],
                "summary": record["summary"],
                "snapshot_ref": record["snapshot_ref"],
            }
            for record in records
        ]

    def _map_interpretation_records(
        self,
        records: list[InterpretationRecord],
    ) -> list[RetrievalInterpretationSummary]:
        mapped: list[RetrievalInterpretationSummary] = []
        for record in records:
            summary = self._summarize_interpretation_body(record["body"])
            item: RetrievalInterpretationSummary = {
                "id": record["id"],
                "domain": record["domain"],
                "kind": record["kind"],
                "subject_type": record["subject_type"],
                "subject_id": record["subject_id"],
                "status": record["status"],
                "confidence": record["confidence"],
            }
            if summary is not None:
                item["summary"] = summary
            mapped.append(item)
        return mapped

    def _map_fact_records(
        self,
        records: list[FactRecord],
    ) -> list[RetrievalFactSummary]:
        mapped: list[RetrievalFactSummary] = []
        for record in records:
            item: RetrievalFactSummary = {
                "id": record["id"],
                "domain": record["domain"],
                "entity_type": record["entity_type"],
                "canonical_key": record["canonical_key"],
                "scope": record["scope"],
            }
            title = self._summarize_fact_attributes(record["attributes"])
            if title is not None:
                item["title"] = title
            mapped.append(item)
        return mapped

    def _summarize_interpretation_body(self, body: dict[str, Any]) -> str | None:
        for key in ("summary", "thesis", "headline", "title"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _summarize_fact_attributes(self, attributes: dict[str, Any]) -> str | None:
        for key in ("title", "name", "label"):
            value = attributes.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _scope_for_layer(self, layer: str, requested_scope: ScopeRef) -> ScopeRef:
        if layer == "personal":
            return requested_scope
        return {"scope": "shared"}

    def _match_pages(
        self,
        pages: list[RenderedPageSummary],
        *,
        layer: str,
        normalized_question: str,
        query_tokens: list[str],
        structured_lookup: bool,
        profile_context: ProfileContext | None,
    ) -> list[tuple[RenderedPageSummary, RetrievalMatchExplanation]]:
        exact_matches: list[tuple[RenderedPageSummary, RetrievalMatchExplanation]] = []
        scored_pages: list[
            tuple[int, int, int, RenderedPageSummary, RetrievalMatchExplanation]
        ] = []

        for index, page in enumerate(pages):
            match_result = self._score_page(
                page,
                normalized_question=normalized_question,
                query_tokens=query_tokens,
                structured_lookup=structured_lookup,
            )
            score = match_result["score"]
            if score <= 0:
                continue
            profile_boost_applied = False
            if score == 100:
                explanation = self._build_match_explanation(
                    layer=layer,
                    page=page,
                    match_result=match_result,
                    profile_boost_applied=False,
                )
                exact_matches.append((page, explanation))
            profile_bonus = 0
            if (
                profile_context is not None
                and page["snapshot_ref"].get("profile_version")
                == profile_context["profile_version"]
            ):
                profile_bonus = 1
                profile_boost_applied = True
            explanation = self._build_match_explanation(
                layer=layer,
                page=page,
                match_result=match_result,
                profile_boost_applied=profile_boost_applied,
            )
            scored_pages.append((score, profile_bonus, -index, page, explanation))

        scored_pages.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            ),
            reverse=True,
        )
        if exact_matches:
            return exact_matches
        return [(page, explanation) for _, _, _, page, explanation in scored_pages]

    def _score_page(
        self,
        page: RenderedPageSummary,
        *,
        normalized_question: str,
        query_tokens: list[str],
        structured_lookup: bool,
    ) -> dict[str, Any]:
        normalized_fields = {
            "record_id": self._normalize(page["record_id"]),
            "title": self._normalize(page["title"]),
            "path": self._normalize(page["path"]),
        }

        exact_matches = [
            field_name
            for field_name, field_value in normalized_fields.items()
            if field_value == normalized_question
        ]
        if exact_matches:
            return {
                "score": 100,
                "match_type": "exact",
                "matched_fields": exact_matches,
            }

        contains_matches = [
            field_name
            for field_name, field_value in normalized_fields.items()
            if normalized_question in field_value
        ]
        if contains_matches:
            return {
                "score": 80,
                "match_type": "contains",
                "matched_fields": contains_matches,
            }

        if structured_lookup:
            return {
                "score": 0,
                "match_type": "structured_miss",
                "matched_fields": [],
            }

        if not query_tokens:
            return {"score": 0, "match_type": "blank_query", "matched_fields": []}

        token_scores = {
            "record_id": self._token_overlap_score(
                query_tokens,
                self._tokenize(page["record_id"]),
            ),
            "title": self._token_overlap_score(
                query_tokens,
                self._tokenize(page["title"]),
            ),
            "path": self._token_overlap_score(
                query_tokens,
                self._tokenize(page["path"]),
            ),
        }
        best_score = max(token_scores.values())
        matched_fields = [
            field_name for field_name, score in token_scores.items() if score == best_score and score > 0
        ]
        return {
            "score": best_score,
            "match_type": "token_overlap" if best_score > 0 else "no_match",
            "matched_fields": matched_fields,
        }

    def _build_match_explanation(
        self,
        *,
        layer: str,
        page: RenderedPageSummary,
        match_result: dict[str, Any],
        profile_boost_applied: bool,
    ) -> RetrievalMatchExplanation:
        return {
            "layer": cast(Any, layer),
            "record_id": page["record_id"],
            "score": int(match_result["score"]),
            "match_type": str(match_result["match_type"]),
            "matched_fields": cast(list[str], match_result["matched_fields"]),
            "profile_boost_applied": profile_boost_applied,
        }

    def _token_overlap_score(
        self,
        query_tokens: list[str],
        field_tokens: list[str],
    ) -> int:
        if not field_tokens:
            return 0

        overlap = sum(1 for token in query_tokens if token in field_tokens)
        if overlap == 0:
            return 0
        if overlap == len(query_tokens):
            return 60 + overlap
        if overlap >= max(1, (len(query_tokens) + 1) // 2):
            return 30 + overlap
        return 0

    def _merge_snapshot_ref(
        self,
        matches_by_layer: dict[str, list[RenderedPageSummary]],
    ) -> SnapshotRef | None:
        merged: dict[str, str] = {}

        for layer in self.layer_order:
            pages = matches_by_layer[layer]
            if not pages:
                continue
            snapshot_ref = pages[0]["snapshot_ref"]
            if "fact_snapshot_id" in snapshot_ref and "fact_snapshot_id" not in merged:
                merged["fact_snapshot_id"] = snapshot_ref["fact_snapshot_id"]
            if (
                "interpretation_snapshot_id" in snapshot_ref
                and "interpretation_snapshot_id" not in merged
            ):
                merged["interpretation_snapshot_id"] = snapshot_ref[
                    "interpretation_snapshot_id"
                ]
            if "profile_version" in snapshot_ref and "profile_version" not in merged:
                merged["profile_version"] = snapshot_ref["profile_version"]

        if "fact_snapshot_id" not in merged:
            return None

        return cast(SnapshotRef, merged)

    def _normalize(self, value: str) -> str:
        return " ".join(self._tokenize(value))

    def _tokenize(self, value: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", value.lower())

    def _looks_structured(self, value: str) -> bool:
        return any(marker in value for marker in (":", "/", ".md"))
