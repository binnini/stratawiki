from __future__ import annotations

from typing import Any

from wiki_mcp.schemas.personal_query_answer import (
    PersonalQueryAnswer,
    PersonalQueryCitation,
)
from wiki_mcp.schemas.personal_query_bundle import (
    PersonalQueryBundle,
    PersonalQueryBundleItem,
)
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.retrieval_result import RetrievalResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.services.interfaces.retrieval import RetrievalService


class DefaultPersonalQueryService:
    """Thin orchestration layer that builds an answer on top of retrieval output."""

    layer_order = ("personal", "interpretation", "fact")

    def __init__(self, *, retrieval_service: RetrievalService) -> None:
        self.retrieval_service = retrieval_service

    def query_personal_knowledge(
        self,
        *,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext | None = None,
    ) -> tuple[RetrievalResult, PersonalQueryAnswer]:
        retrieval = self.retrieval_service.retrieve_for_query(
            domain=domain,
            question=question,
            scope_ref=scope_ref,
            profile_context=profile_context,
        )
        input_bundle = self._build_input_bundle(
            question=question,
            scope_ref=scope_ref,
            profile_context=profile_context,
            retrieval=retrieval,
        )
        answer = self._build_answer(question=question, input_bundle=input_bundle)
        return retrieval, answer

    def _build_input_bundle(
        self,
        *,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext | None,
        retrieval: RetrievalResult,
    ) -> PersonalQueryBundle:
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
        return bundle

    def _build_layer_items(
        self,
        layer: str,
        retrieval: RetrievalResult,
    ) -> list[PersonalQueryBundleItem]:
        pages = retrieval.get(f"{layer}_pages", [])
        records = retrieval.get(f"{layer}_records", [])
        explanations = retrieval.get(f"{layer}_explanations", [])
        page_by_id = {
            page["record_id"]: page
            for page in pages
        }
        explanation_by_id = {
            explanation["record_id"]: explanation
            for explanation in explanations
        }
        items: list[PersonalQueryBundleItem] = []
        for record in records:
            page = page_by_id.get(record["id"])
            explanation = explanation_by_id.get(record["id"])
            items.append(
                {
                    "layer": layer,
                    "record_id": record["id"],
                    "title": self._record_title(layer, record, page),
                    "summary": self._record_summary(layer, record, page),
                    **({"kind": record["kind"]} if "kind" in record else {}),
                    **self._item_match_metadata(explanation),
                    **({"path": page["path"]} if page is not None else {}),
                }
            )
        if items:
            return items
        return [
            {
                "layer": layer,
                "record_id": page["record_id"],
                "title": page["title"],
                "summary": self._page_summary(page),
                **self._item_match_metadata(explanation_by_id.get(page["record_id"])),
                "path": page["path"],
            }
            for page in pages
        ]

    def _item_match_metadata(
        self,
        explanation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if explanation is None:
            return {}
        metadata: dict[str, Any] = {
            "retrieval_score": explanation["score"],
            "matched_fields": explanation["matched_fields"],
            "match_reason": self._match_reason(explanation),
        }
        return metadata

    def _record_title(
        self,
        layer: str,
        record: dict[str, Any],
        page: RenderedPageSummary | None,
    ) -> str:
        if layer == "fact":
            return str(record.get("title") or record.get("canonical_key") or record["id"])
        return str(record.get("title") or record.get("subject_id") or record["id"])

    def _record_summary(
        self,
        layer: str,
        record: dict[str, Any],
        page: RenderedPageSummary | None,
    ) -> str:
        if layer == "personal":
            summary = record.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary.strip()
        if layer == "interpretation":
            summary = record.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary.strip()
            status = record.get("status")
            confidence = record.get("confidence")
            return f"Interpretation status: {status}, confidence: {confidence}"
        if layer == "fact":
            parts = [record.get("entity_type"), record.get("canonical_key")]
            return " / ".join(str(part) for part in parts if part)
        if page is not None:
            return self._page_summary(page)
        return str(record.get("id"))

    def _page_summary(self, page: RenderedPageSummary) -> str:
        metadata_summary = page["metadata"].get("summary")
        if isinstance(metadata_summary, str) and metadata_summary.strip():
            return metadata_summary.strip()
        return f"Rendered {page['layer']} page at {page['path']}"

    def _build_answer(
        self,
        *,
        question: str,
        input_bundle: PersonalQueryBundle,
    ) -> PersonalQueryAnswer:
        lead_item = self._select_lead_item(input_bundle)
        if lead_item is None:
            answer_summary = "No matching personal, interpretation, or fact context was found."
            answer_rationale = "No retrieval candidate cleared the current matching threshold."
            citations: list[PersonalQueryCitation] = []
            answer_markdown = self._render_answer_markdown(
                question=question,
                answer_summary=answer_summary,
                answer_rationale=answer_rationale,
                input_bundle=input_bundle,
            )
            return {
                "answer_type": "personal_query_answer",
                "generation_strategy": "deterministic_summary_bundle_v1",
                "question": question,
                "answer_summary": answer_summary,
                "answer_rationale": answer_rationale,
                "answer_markdown": answer_markdown,
                "citations": citations,
                "input_bundle": input_bundle,
            }

        if lead_item.get("kind") == "career_transition_plan":
            return self._build_career_transition_plan_answer(
                question=question,
                input_bundle=input_bundle,
                lead_item=lead_item,
            )

        layer_label = lead_item["layer"]
        answer_summary = (
            f"Best current {layer_label} context: {lead_item['title']}. "
            f"{lead_item['summary']}"
        )
        answer_rationale = self._build_answer_rationale(input_bundle, lead_item)
        citations = self._build_citations(input_bundle)

        answer_markdown = self._render_answer_markdown(
            question=question,
            answer_summary=answer_summary,
            answer_rationale=answer_rationale,
            input_bundle=input_bundle,
        )
        return {
            "answer_type": "personal_query_answer",
            "generation_strategy": "deterministic_summary_bundle_v1",
            "question": question,
            "answer_summary": answer_summary,
            "answer_rationale": answer_rationale,
            "answer_markdown": answer_markdown,
            "citations": citations,
            "input_bundle": input_bundle,
        }

    def _build_career_transition_plan_answer(
        self,
        *,
        question: str,
        input_bundle: PersonalQueryBundle,
        lead_item: PersonalQueryBundleItem,
    ) -> PersonalQueryAnswer:
        answer_summary = (
            f"Current career transition plan focus: {lead_item['title']}. "
            f"{lead_item['summary']}"
        )
        answer_rationale = self._build_answer_rationale(input_bundle, lead_item)
        recommended_actions = self._build_career_transition_actions(input_bundle, lead_item)
        answer_markdown = self._render_career_transition_plan_markdown(
            question=question,
            answer_summary=answer_summary,
            answer_rationale=answer_rationale,
            input_bundle=input_bundle,
            recommended_actions=recommended_actions,
        )
        return {
            "answer_type": "personal_query_answer",
            "generation_strategy": "deterministic_summary_bundle_v1",
            "personal_family": "career_transition_plan",
            "question": question,
            "answer_summary": answer_summary,
            "answer_rationale": answer_rationale,
            "answer_markdown": answer_markdown,
            "recommended_actions": recommended_actions,
            "citations": self._build_citations(input_bundle),
            "input_bundle": input_bundle,
        }

    def _build_answer_rationale(
        self,
        input_bundle: PersonalQueryBundle,
        lead_item: PersonalQueryBundleItem,
    ) -> str:
        lines = [
            (
                f"Selected {lead_item['layer']} context first because the current layer order is "
                "personal -> interpretation -> fact."
            )
        ]
        if "match_reason" in lead_item:
            rationale = f"Top match reason: {lead_item['match_reason']}."
            if "retrieval_score" in lead_item:
                rationale = f"{rationale[:-1]} with score {lead_item['retrieval_score']}."
            lines.append(rationale)
        sibling_counts = [
            f"{len(input_bundle['personal_context'])} personal",
            f"{len(input_bundle['interpretation_context'])} interpretation",
            f"{len(input_bundle['fact_context'])} fact",
        ]
        lines.append(
            "Context bundle includes "
            + ", ".join(sibling_counts)
            + " matches after layer-aware ranking."
        )
        return " ".join(lines)

    def _build_career_transition_actions(
        self,
        input_bundle: PersonalQueryBundle,
        lead_item: PersonalQueryBundleItem,
    ) -> list[str]:
        actions = [
            f"Prioritize the transition direction captured in {lead_item['title'].lower()}.",
        ]
        if input_bundle["interpretation_context"]:
            top_interpretation = input_bundle["interpretation_context"][0]
            actions.append(
                "Use the strongest shared market signal as a weekly checkpoint: "
                f"{top_interpretation['summary']}"
            )
        if input_bundle["fact_context"]:
            top_fact = input_bundle["fact_context"][0]
            actions.append(
                f"Turn the top supporting fact into a concrete next step: {top_fact['title']}."
            )
        return actions[:3]

    def _select_lead_item(
        self,
        input_bundle: PersonalQueryBundle,
    ) -> PersonalQueryBundleItem | None:
        for key in ("personal_context", "interpretation_context", "fact_context"):
            items = input_bundle[key]
            if items:
                return items[0]
        return None

    def _build_citations(
        self,
        input_bundle: PersonalQueryBundle,
    ) -> list[PersonalQueryCitation]:
        citations: list[PersonalQueryCitation] = []
        for key in ("personal_context", "interpretation_context", "fact_context"):
            for item in input_bundle[key]:
                citations.append(
                    {
                        "layer": item["layer"],
                        "record_id": item["record_id"],
                        "title": item["title"],
                        "path": item.get("path"),
                    }
                )
        return citations

    def _render_answer_markdown(
        self,
        *,
        question: str,
        answer_summary: str,
        answer_rationale: str,
        input_bundle: PersonalQueryBundle,
    ) -> str:
        lines = [
            "# Personal Knowledge Answer",
            "",
            f"Question: {question}",
            "",
            answer_summary,
            "",
            "Rationale:",
            answer_rationale,
        ]
        for key, heading in (
            ("personal_context", "Personal Context"),
            ("interpretation_context", "Shared Interpretation Context"),
            ("fact_context", "Fact Context"),
        ):
            items = input_bundle[key]
            if not items:
                continue
            lines.extend(["", f"## {heading}"])
            for item in items:
                detail = f"- {item['title']}: {item['summary']}"
                if "match_reason" in item:
                    detail += f" ({item['match_reason']}"
                    if "retrieval_score" in item:
                        detail += f", score={item['retrieval_score']}"
                    detail += ")"
                lines.append(detail)
        return "\n".join(lines)

    def _render_career_transition_plan_markdown(
        self,
        *,
        question: str,
        answer_summary: str,
        answer_rationale: str,
        input_bundle: PersonalQueryBundle,
        recommended_actions: list[str],
    ) -> str:
        goals = []
        profile_context = input_bundle.get("profile_context")
        if isinstance(profile_context, dict):
            goals = [str(goal) for goal in profile_context.get("goals", [])[:3]]

        lines = [
            "# Career Transition Plan",
            "",
            f"Question: {question}",
            "",
            "## Direction",
            answer_summary,
            "",
            "## Why This Plan",
            answer_rationale,
        ]
        if goals:
            lines.extend(["", "## Active Goals"])
            lines.extend(f"- {goal}" for goal in goals)
        if recommended_actions:
            lines.extend(["", "## Recommended Actions"])
            lines.extend(f"- {action}" for action in recommended_actions)
        for key, heading in (
            ("personal_context", "Plan Context"),
            ("interpretation_context", "Market Signals"),
            ("fact_context", "Supporting Evidence"),
        ):
            items = input_bundle[key]
            if not items:
                continue
            lines.extend(["", f"## {heading}"])
            for item in items:
                detail = f"- {item['title']}: {item['summary']}"
                if "match_reason" in item:
                    detail += f" ({item['match_reason']}"
                    if "retrieval_score" in item:
                        detail += f", score={item['retrieval_score']}"
                    detail += ")"
                lines.append(detail)
        return "\n".join(lines)

    def _match_reason(self, explanation: dict[str, Any]) -> str:
        matched_fields = explanation.get("matched_fields", [])
        field_label = ", ".join(matched_fields) if matched_fields else "no field"
        match_type = explanation.get("match_type", "unknown")
        profile_suffix = ""
        if explanation.get("profile_boost_applied"):
            profile_suffix = " with profile-version preference"
        return f"{match_type} match on {field_label}{profile_suffix}"
