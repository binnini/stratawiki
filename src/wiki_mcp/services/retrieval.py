from __future__ import annotations

import re
from typing import cast

from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.retrieval_result import RetrievalResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.services.interfaces.page_reads import PageReadService


class DefaultRetrievalService:
    """Minimal structured retrieval across rendered Personal, Interpretation, and Fact pages."""

    layer_order = ("personal", "interpretation", "fact")

    def __init__(
        self,
        *,
        page_read_service: PageReadService,
        page_scan_limit: int = 50,
        layer_result_limit: int = 5,
    ) -> None:
        self.page_read_service = page_read_service
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
            }

        query_tokens = self._tokenize(question)
        structured_lookup = self._looks_structured(question)
        matches_by_layer: dict[str, list[RenderedPageSummary]] = {}

        for layer in self.layer_order:
            pages = self.page_read_service.list_pages(
                domain=domain,
                scope_ref=self._scope_for_layer(layer, scope_ref),
                layer=layer,
                limit=self.page_scan_limit,
            )
            matches_by_layer[layer] = self._match_pages(
                pages,
                normalized_question=normalized_question,
                query_tokens=query_tokens,
                structured_lookup=structured_lookup,
                profile_context=profile_context,
            )[: self.layer_result_limit]

        result: RetrievalResult = {
            "personal_ids": [page["record_id"] for page in matches_by_layer["personal"]],
            "interpretation_ids": [
                page["record_id"] for page in matches_by_layer["interpretation"]
            ],
            "fact_ids": [page["record_id"] for page in matches_by_layer["fact"]],
        }

        snapshot_ref = self._merge_snapshot_ref(matches_by_layer)
        if snapshot_ref is not None:
            result["snapshot_ref"] = snapshot_ref

        return result

    def _scope_for_layer(self, layer: str, requested_scope: ScopeRef) -> ScopeRef:
        if layer == "personal":
            return requested_scope
        return {"scope": "shared"}

    def _match_pages(
        self,
        pages: list[RenderedPageSummary],
        *,
        normalized_question: str,
        query_tokens: list[str],
        structured_lookup: bool,
        profile_context: ProfileContext | None,
    ) -> list[RenderedPageSummary]:
        exact_matches: list[RenderedPageSummary] = []
        scored_pages: list[tuple[int, int, int, RenderedPageSummary]] = []

        for index, page in enumerate(pages):
            score = self._score_page(
                page,
                normalized_question=normalized_question,
                query_tokens=query_tokens,
                structured_lookup=structured_lookup,
            )
            if score <= 0:
                continue
            if score == 100:
                exact_matches.append(page)
            profile_bonus = 0
            if (
                profile_context is not None
                and page["snapshot_ref"].get("profile_version")
                == profile_context["profile_version"]
            ):
                profile_bonus = 1
            scored_pages.append((score, profile_bonus, -index, page))

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
        return [page for _, _, _, page in scored_pages]

    def _score_page(
        self,
        page: RenderedPageSummary,
        *,
        normalized_question: str,
        query_tokens: list[str],
        structured_lookup: bool,
    ) -> int:
        fields = (
            self._normalize(page["record_id"]),
            self._normalize(page["title"]),
            self._normalize(page["path"]),
        )

        if any(field == normalized_question for field in fields):
            return 100

        if any(normalized_question in field for field in fields):
            return 80

        if structured_lookup:
            return 0

        if not query_tokens:
            return 0

        token_scores = [
            self._token_overlap_score(query_tokens, self._tokenize(page["record_id"])),
            self._token_overlap_score(query_tokens, self._tokenize(page["title"])),
            self._token_overlap_score(query_tokens, self._tokenize(page["path"])),
        ]
        return max(token_scores)

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
