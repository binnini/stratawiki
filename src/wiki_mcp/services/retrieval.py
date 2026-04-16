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
from wiki_mcp.services.interfaces.page_reads import PageReadService
from wiki_mcp.services.interfaces.repositories import (
    FactRepository,
    InterpretationRepository,
    PersonalRepository,
)


class DefaultRetrievalService:
    """Minimal structured retrieval across rendered and canonical layer candidates."""

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
        matched_ids_by_layer: dict[str, list[str]] = {}
        matched_pages_by_layer: dict[str, list[RenderedPageSummary]] = {}
        explanations_by_layer: dict[str, list[RetrievalMatchExplanation]] = {}
        prefetched_records_by_layer: dict[str, dict[str, dict[str, Any]]] = {}

        for layer in self.layer_order:
            pages = self.page_read_service.list_pages(
                domain=domain,
                scope_ref=self._scope_for_layer(layer, scope_ref),
                layer=layer,
                limit=self.page_scan_limit,
            )
            records_by_id = self._collect_records_for_layer(
                layer=layer,
                domain=domain,
                pages=pages,
                normalized_question=normalized_question,
                query_tokens=query_tokens,
                requested_scope=scope_ref,
            )
            prefetched_records_by_layer[layer] = records_by_id
            record_summaries = self._record_summaries_for_layer(
                layer=layer,
                records=list(records_by_id.values()),
            )
            matched_candidates = self._match_candidates(
                self._build_layer_candidates(pages=pages, records_by_id=records_by_id),
                layer=layer,
                normalized_question=normalized_question,
                query_tokens=query_tokens,
                structured_lookup=structured_lookup,
                profile_context=profile_context if layer == "personal" else None,
                record_summaries=record_summaries,
            )[: self.layer_result_limit]
            matched_ids_by_layer[layer] = [
                str(candidate["record_id"]) for candidate, _ in matched_candidates
            ]
            matched_pages_by_layer[layer] = [
                cast(RenderedPageSummary, candidate["page"])
                for candidate, _ in matched_candidates
                if candidate["page"] is not None
            ]
            explanations_by_layer[layer] = [
                {
                    **explanation,
                    "rank": index + 1,
                }
                for index, (_, explanation) in enumerate(matched_candidates)
            ]

        result: RetrievalResult = {
            "personal_ids": matched_ids_by_layer["personal"],
            "interpretation_ids": matched_ids_by_layer["interpretation"],
            "fact_ids": matched_ids_by_layer["fact"],
            "personal_pages": matched_pages_by_layer["personal"],
            "interpretation_pages": matched_pages_by_layer["interpretation"],
            "fact_pages": matched_pages_by_layer["fact"],
            "personal_explanations": explanations_by_layer["personal"],
            "interpretation_explanations": explanations_by_layer["interpretation"],
            "fact_explanations": explanations_by_layer["fact"],
        }
        result.update(
            self._hydrate_records(
                matched_ids_by_layer,
                requested_scope=scope_ref,
                prefetched_records_by_layer=prefetched_records_by_layer,
            )
        )

        snapshot_ref = self._merge_snapshot_ref(
            matched_pages_by_layer=matched_pages_by_layer,
            matched_ids_by_layer=matched_ids_by_layer,
            prefetched_records_by_layer=prefetched_records_by_layer,
        )
        if snapshot_ref is not None:
            result["snapshot_ref"] = snapshot_ref

        return result

    def _collect_records_for_layer(
        self,
        *,
        layer: str,
        domain: str,
        pages: list[RenderedPageSummary],
        normalized_question: str,
        query_tokens: list[str],
        requested_scope: ScopeRef,
    ) -> dict[str, dict[str, Any]]:
        records_by_id = {
            record["id"]: record
            for record in self._prefetch_records(
                layer=layer,
                pages=pages,
                requested_scope=requested_scope,
            )
        }
        for record in self._list_records_for_retrieval(
            layer=layer,
            domain=domain,
            query_text=normalized_question,
            query_tokens=query_tokens,
            requested_scope=requested_scope,
        ):
            records_by_id.setdefault(record["id"], record)
        return records_by_id

    def _hydrate_records(
        self,
        matched_ids_by_layer: dict[str, list[str]],
        *,
        requested_scope: ScopeRef,
        prefetched_records_by_layer: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> RetrievalResult:
        hydrated: dict[str, Any] = {}
        prefetched_records_by_layer = prefetched_records_by_layer or {}

        personal_ids = matched_ids_by_layer["personal"]
        if personal_ids and self.personal_repository is not None:
            personal_records = cast(
                dict[str, PersonalRecord] | None,
                prefetched_records_by_layer.get("personal"),
            )
            if personal_records is None:
                personal_records = {
                    record["id"]: record
                    for record in self.personal_repository.get_by_ids(personal_ids, requested_scope)
                }
            hydrated["personal_records"] = self._ordered_records(
                personal_ids,
                self._map_personal_records(
                    [
                        personal_records[record_id]
                        for record_id in personal_ids
                        if record_id in personal_records
                    ]
                ),
            )

        interpretation_ids = matched_ids_by_layer["interpretation"]
        if interpretation_ids and self.interpretation_repository is not None:
            interpretation_records = cast(
                dict[str, InterpretationRecord] | None,
                prefetched_records_by_layer.get("interpretation"),
            )
            if interpretation_records is None:
                interpretation_records = {
                    record["id"]: record
                    for record in self.interpretation_repository.get_by_ids(
                        interpretation_ids,
                        self._scope_for_layer("interpretation", requested_scope),
                    )
                }
            hydrated["interpretation_records"] = self._ordered_records(
                interpretation_ids,
                self._map_interpretation_records(
                    [
                        interpretation_records[record_id]
                        for record_id in interpretation_ids
                        if record_id in interpretation_records
                    ]
                ),
            )

        fact_ids = matched_ids_by_layer["fact"]
        if fact_ids and self.fact_repository is not None:
            fact_records = cast(
                dict[str, FactRecord] | None,
                prefetched_records_by_layer.get("fact"),
            )
            if fact_records is None:
                fact_records = {
                    record["id"]: record
                    for record in self.fact_repository.get_by_ids(
                        fact_ids,
                        self._scope_for_layer("fact", requested_scope),
                    )
                }
            hydrated["fact_records"] = self._ordered_records(
                fact_ids,
                self._map_fact_records(
                    [fact_records[record_id] for record_id in fact_ids if record_id in fact_records]
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

    def _summarize_fact_summary(self, attributes: dict[str, Any]) -> str | None:
        for key in ("summary", "description", "headline"):
            value = attributes.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _scope_for_layer(self, layer: str, requested_scope: ScopeRef) -> ScopeRef:
        if layer == "personal":
            return requested_scope
        return {"scope": "shared"}

    def _build_layer_candidates(
        self,
        *,
        pages: list[RenderedPageSummary],
        records_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        page_ids = set()
        for page in pages:
            record_id = page["record_id"]
            page_ids.add(record_id)
            candidates.append(
                {
                    "record_id": record_id,
                    "page": page,
                    "record": records_by_id.get(record_id),
                }
            )
        for record_id, record in records_by_id.items():
            if record_id in page_ids:
                continue
            candidates.append(
                {
                    "record_id": record_id,
                    "page": None,
                    "record": record,
                }
            )
        return candidates

    def _match_candidates(
        self,
        candidates: list[dict[str, Any]],
        *,
        layer: str,
        normalized_question: str,
        query_tokens: list[str],
        structured_lookup: bool,
        profile_context: ProfileContext | None,
        record_summaries: dict[str, dict[str, str]],
    ) -> list[tuple[dict[str, Any], RetrievalMatchExplanation]]:
        exact_matches: list[tuple[dict[str, Any], RetrievalMatchExplanation]] = []
        scored_candidates: list[tuple[int, int, int, dict[str, Any], RetrievalMatchExplanation]] = []

        for index, candidate in enumerate(candidates):
            record_id = str(candidate["record_id"])
            page = cast(RenderedPageSummary | None, candidate["page"])
            match_result = self._score_candidate(
                page=page,
                record_id=record_id,
                normalized_question=normalized_question,
                query_tokens=query_tokens,
                structured_lookup=structured_lookup,
                record_summary=record_summaries.get(record_id),
            )
            score = int(match_result["score"])
            if score <= 0:
                continue

            profile_boost_applied = False
            if score == 100:
                explanation = self._build_match_explanation(
                    layer=layer,
                    record_id=record_id,
                    match_result=match_result,
                    profile_boost_applied=False,
                )
                exact_matches.append((candidate, explanation))

            profile_bonus = 0
            if (
                profile_context is not None
                and page is not None
                and page["snapshot_ref"].get("profile_version") == profile_context["profile_version"]
            ):
                profile_bonus = 1
                profile_boost_applied = True

            explanation = self._build_match_explanation(
                layer=layer,
                record_id=record_id,
                match_result=match_result,
                profile_boost_applied=profile_boost_applied,
            )
            scored_candidates.append((score, profile_bonus, -index, candidate, explanation))

        scored_candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            ),
            reverse=True,
        )
        if exact_matches:
            return exact_matches
        return [(candidate, explanation) for _, _, _, candidate, explanation in scored_candidates]

    def _score_candidate(
        self,
        *,
        page: RenderedPageSummary | None,
        record_id: str,
        normalized_question: str,
        query_tokens: list[str],
        structured_lookup: bool,
        record_summary: dict[str, str] | None,
    ) -> dict[str, Any]:
        normalized_fields = self._normalized_search_fields(
            page=page,
            record_id=record_id,
            record_summary=record_summary,
        )

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
                "matched_token_count": len(query_tokens),
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
                "matched_token_count": len(query_tokens),
            }

        if structured_lookup:
            return {
                "score": 0,
                "match_type": "structured_miss",
                "matched_fields": [],
                "matched_token_count": 0,
            }

        if not query_tokens:
            return {
                "score": 0,
                "match_type": "blank_query",
                "matched_fields": [],
                "matched_token_count": 0,
            }

        token_scores = {
            field_name: self._token_overlap_score(query_tokens, self._tokenize(field_value))
            for field_name, field_value in normalized_fields.items()
        }
        best_score = max(token_scores.values(), default=0)
        matched_fields = [
            field_name for field_name, score in token_scores.items() if score == best_score and score > 0
        ]
        return {
            "score": best_score,
            "match_type": "token_overlap" if best_score > 0 else "no_match",
            "matched_fields": matched_fields,
            "matched_token_count": max(
                (
                    len(set(query_tokens) & set(self._tokenize(field_value)))
                    for field_value in normalized_fields.values()
                ),
                default=0,
            ),
        }

    def _normalized_search_fields(
        self,
        *,
        page: RenderedPageSummary | None,
        record_id: str,
        record_summary: dict[str, str] | None,
    ) -> dict[str, str]:
        fields = {
            "record_id": self._normalize(record_id),
        }
        if page is not None:
            fields["title"] = self._normalize(page["title"])
            fields["path"] = self._normalize(page["path"])
            page_summary = self._page_summary(page)
            if page_summary:
                fields["page_summary"] = self._normalize(page_summary)
        if record_summary is not None:
            for field_name, field_value in record_summary.items():
                normalized_value = self._normalize(field_value)
                if normalized_value:
                    fields[field_name] = normalized_value
        return fields

    def _page_summary(self, page: RenderedPageSummary) -> str:
        summary = page["metadata"].get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
        return ""

    def _prefetch_records(
        self,
        *,
        layer: str,
        pages: list[RenderedPageSummary],
        requested_scope: ScopeRef,
    ) -> list[dict[str, Any]]:
        page_ids = [page["record_id"] for page in pages]
        if not page_ids:
            return []

        if layer == "personal" and self.personal_repository is not None:
            return cast(list[dict[str, Any]], self.personal_repository.get_by_ids(page_ids, requested_scope))
        if layer == "interpretation" and self.interpretation_repository is not None:
            return cast(
                list[dict[str, Any]],
                self.interpretation_repository.get_by_ids(
                    page_ids,
                    self._scope_for_layer(layer, requested_scope),
                ),
            )
        if layer == "fact" and self.fact_repository is not None:
            return cast(
                list[dict[str, Any]],
                self.fact_repository.get_by_ids(
                    page_ids,
                    self._scope_for_layer(layer, requested_scope),
                ),
            )
        return []

    def _list_records_for_retrieval(
        self,
        *,
        layer: str,
        domain: str,
        query_text: str,
        query_tokens: list[str],
        requested_scope: ScopeRef,
    ) -> list[dict[str, Any]]:
        if layer == "personal" and self.personal_repository is not None:
            return cast(
                list[dict[str, Any]],
                self.personal_repository.search_for_retrieval(
                    domain=domain,
                    scope_ref=requested_scope,
                    query_text=query_text,
                    query_tokens=query_tokens,
                    limit=self.page_scan_limit,
                ),
            )
        shared_scope = self._scope_for_layer(layer, requested_scope)
        if layer == "interpretation" and self.interpretation_repository is not None:
            return cast(
                list[dict[str, Any]],
                self.interpretation_repository.search_for_retrieval(
                    domain=domain,
                    scope_ref=shared_scope,
                    query_text=query_text,
                    query_tokens=query_tokens,
                    limit=self.page_scan_limit,
                ),
            )
        if layer == "fact" and self.fact_repository is not None:
            return cast(
                list[dict[str, Any]],
                self.fact_repository.search_for_retrieval(
                    domain=domain,
                    scope_ref=shared_scope,
                    query_text=query_text,
                    query_tokens=query_tokens,
                    limit=self.page_scan_limit,
                ),
            )
        return []

    def _record_summaries_for_layer(
        self,
        *,
        layer: str,
        records: list[dict[str, Any]],
    ) -> dict[str, dict[str, str]]:
        if layer == "personal":
            return {
                record["id"]: self._personal_record_search_fields(cast(PersonalRecord, record))
                for record in records
            }
        if layer == "interpretation":
            return {
                record["id"]: self._interpretation_record_search_fields(
                    cast(InterpretationRecord, record)
                )
                for record in records
            }
        if layer == "fact":
            return {
                record["id"]: self._fact_record_search_fields(cast(FactRecord, record))
                for record in records
            }
        return {}

    def _personal_record_search_fields(self, record: PersonalRecord) -> dict[str, str]:
        fields: dict[str, str] = {}
        if record["title"].strip():
            fields["canonical_title"] = record["title"].strip()
        if record["summary"].strip():
            fields["canonical_summary"] = record["summary"].strip()
        if record["kind"].strip():
            fields["kind"] = record["kind"].strip()
        return fields

    def _interpretation_record_search_fields(
        self,
        record: InterpretationRecord,
    ) -> dict[str, str]:
        fields: dict[str, str] = {}
        summary = self._summarize_interpretation_body(record["body"])
        if summary is not None:
            fields["canonical_summary"] = summary
        if record["subject_id"].strip():
            fields["subject_id"] = record["subject_id"].strip()
        if record["kind"].strip():
            fields["kind"] = record["kind"].strip()
        return fields

    def _fact_record_search_fields(self, record: FactRecord) -> dict[str, str]:
        fields: dict[str, str] = {}
        title = self._summarize_fact_attributes(record["attributes"])
        if title is not None:
            fields["canonical_title"] = title
        summary = self._summarize_fact_summary(record["attributes"])
        if summary is not None:
            fields["canonical_summary"] = summary
        if record["canonical_key"].strip():
            fields["canonical_key"] = record["canonical_key"].strip()
        if record["entity_type"].strip():
            fields["entity_type"] = record["entity_type"].strip()
        return fields

    def _build_match_explanation(
        self,
        *,
        layer: str,
        record_id: str,
        match_result: dict[str, Any],
        profile_boost_applied: bool,
    ) -> RetrievalMatchExplanation:
        return {
            "layer": cast(Any, layer),
            "record_id": record_id,
            "rank": 0,
            "score": int(match_result["score"]),
            "match_type": str(match_result["match_type"]),
            "matched_fields": cast(list[str], match_result["matched_fields"]),
            "matched_token_count": int(match_result["matched_token_count"]),
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
        *,
        matched_pages_by_layer: dict[str, list[RenderedPageSummary]],
        matched_ids_by_layer: dict[str, list[str]],
        prefetched_records_by_layer: dict[str, dict[str, dict[str, Any]]],
    ) -> SnapshotRef | None:
        merged: dict[str, str] = {}

        for layer in self.layer_order:
            pages = matched_pages_by_layer[layer]
            snapshot_ref: SnapshotRef | None
            if pages:
                snapshot_ref = pages[0]["snapshot_ref"]
            else:
                record_ids = matched_ids_by_layer[layer]
                if not record_ids:
                    continue
                snapshot_ref = self._snapshot_ref_from_record(
                    layer=layer,
                    record=prefetched_records_by_layer.get(layer, {}).get(record_ids[0]),
                )
            if snapshot_ref is None:
                continue
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

    def _snapshot_ref_from_record(
        self,
        *,
        layer: str,
        record: dict[str, Any] | None,
    ) -> SnapshotRef | None:
        if record is None:
            return None
        if layer == "personal":
            return cast(PersonalRecord, record)["snapshot_ref"]
        if layer == "interpretation":
            return {
                "fact_snapshot_id": cast(InterpretationRecord, record)["fact_snapshot_id"]
            }
        return None

    def _normalize(self, value: str) -> str:
        return " ".join(self._tokenize(value))

    def _tokenize(self, value: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", value.lower())

    def _looks_structured(self, value: str) -> bool:
        return any(marker in value for marker in (":", "/", ".md"))
