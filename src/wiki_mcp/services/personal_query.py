from __future__ import annotations

from wiki_mcp.schemas.personal_query_bundle import (
    PersonalQueryBundle,
    PersonalQueryBundleItem,
)
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.retrieval_result import RetrievalResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.services.interfaces.retrieval import RetrievalService


class PersonalQueryOrchestrator:
    """Build user-facing personal query bundles on top of retrieval output.

    This service intentionally stops before final answer generation. LLM-facing
    answer synthesis will be introduced through the newer orchestration and
    gateway layers defined in the docs.
    """

    def __init__(self, *, retrieval_service: RetrievalService) -> None:
        self.retrieval_service = retrieval_service

    def build_query_bundle(
        self,
        *,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext | None = None,
    ) -> tuple[RetrievalResult, PersonalQueryBundle]:
        retrieval = self.retrieval_service.retrieve_for_query(
            domain=domain,
            question=question,
            scope_ref=scope_ref,
            profile_context=profile_context,
        )
        bundle: PersonalQueryBundle = {
            "question": question,
            "scope_ref": scope_ref,
            "personal_context": self._build_layer_items("personal", retrieval),
            "interpretation_context": self._build_layer_items("interpretation", retrieval),
            "fact_context": self._build_layer_items("fact", retrieval),
        }
        if profile_context is not None:
            bundle["profile_context"] = {
                "user_id": profile_context["user_id"],
                "tenant_id": profile_context["tenant_id"],
                "domain": profile_context["domain"],
                "profile_version": profile_context["profile_version"],
                "goals": profile_context["goals"],
                "preferences": profile_context["preferences"],
                "attributes": profile_context["attributes"],
            }
        if "snapshot_ref" in retrieval:
            bundle["snapshot_ref"] = retrieval["snapshot_ref"]
        return retrieval, bundle

    def _build_layer_items(
        self,
        layer: str,
        retrieval: RetrievalResult,
    ) -> list[PersonalQueryBundleItem]:
        records = retrieval.get(f"{layer}_records", [])
        explanations = retrieval.get(f"{layer}_explanations", [])
        explanation_by_id = {
            explanation["record_id"]: explanation
            for explanation in explanations
        }
        items: list[PersonalQueryBundleItem] = []
        for record in records:
            explanation = explanation_by_id.get(record["id"])
            item: PersonalQueryBundleItem = {
                "layer": layer,
                "record_id": record["id"],
                "title": self._record_title(layer, record),
                "summary": self._record_summary(layer, record),
            }
            if "kind" in record:
                item["kind"] = record["kind"]
            if explanation is not None:
                item["retrieval_rank"] = explanation["rank"]
                item["retrieval_score"] = explanation["score"]
                item["matched_token_count"] = explanation["matched_token_count"]
                item["matched_fields"] = explanation["matched_fields"]
                item["has_rendered_page"] = explanation["has_rendered_page"]
                item["match_reason"] = explanation["match_type"]
            items.append(item)
        return items

    def _record_title(self, layer: str, record: dict[str, object]) -> str:
        if layer == "fact":
            return str(record.get("title") or record.get("canonical_key") or record["id"])
        return str(record.get("title") or record.get("subject_id") or record["id"])

    def _record_summary(self, layer: str, record: dict[str, object]) -> str:
        if layer == "personal":
            return str(record.get("summary") or record["id"])
        if layer == "interpretation":
            return str(
                record.get("summary")
                or f"status={record.get('status')} confidence={record.get('confidence')}"
            )
        return str(record.get("title") or record.get("canonical_key") or record["id"])
