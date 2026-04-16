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
        page_by_id = {
            page["record_id"]: page
            for page in pages
        }
        items: list[PersonalQueryBundleItem] = []
        for record in records:
            page = page_by_id.get(record["id"])
            items.append(
                {
                    "layer": layer,
                    "record_id": record["id"],
                    "title": self._record_title(layer, record, page),
                    "summary": self._record_summary(layer, record, page),
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
                "path": page["path"],
            }
            for page in pages
        ]

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
            citations: list[PersonalQueryCitation] = []
        else:
            layer_label = lead_item["layer"]
            answer_summary = (
                f"Best current {layer_label} context: {lead_item['title']}. "
                f"{lead_item['summary']}"
            )
            citations = self._build_citations(input_bundle)

        answer_markdown = self._render_answer_markdown(
            question=question,
            answer_summary=answer_summary,
            input_bundle=input_bundle,
        )
        return {
            "question": question,
            "answer_summary": answer_summary,
            "answer_markdown": answer_markdown,
            "citations": citations,
            "input_bundle": input_bundle,
        }

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
        input_bundle: PersonalQueryBundle,
    ) -> str:
        lines = [
            "# Personal Knowledge Answer",
            "",
            f"Question: {question}",
            "",
            answer_summary,
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
                lines.append(f"- {item['title']}: {item['summary']}")
        return "\n".join(lines)
