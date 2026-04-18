from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from uuid import uuid4

from wiki_mcp.adapters.llm.gateway import LLMGateway
from wiki_mcp.schemas.personal_query_answer import (
    PersonalQueryAnswer,
    PersonalQueryCitation,
    PersonalQueryProvenance,
    PersonalQueryRationaleItem,
)
from wiki_mcp.schemas.personal_query_bundle import (
    PersonalQueryBundle,
    PersonalQueryBundleItem,
)
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.retrieval_result import RetrievalResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.services.interfaces.repositories import PersonalRepository, RenderingRepository
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
        if "retrieval_metadata" in retrieval:
            bundle["retrieval_metadata"] = retrieval["retrieval_metadata"]
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
            path = record.get("body_path") or record.get("path")
            if isinstance(path, str) and path:
                item["path"] = path
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


class PersonalKnowledgeQueryService:
    """Execute the first end-to-end personal query flow on top of curated retrieval."""

    prompt_id = "personal.query.answer"
    prompt_version = "personal.query.answer.v1"
    generation_strategy = "curated_retrieval_llm_v1"

    def __init__(
        self,
        *,
        orchestrator: PersonalQueryOrchestrator,
        llm_gateway: LLMGateway,
        personal_repository: PersonalRepository | None = None,
        rendering_repository: RenderingRepository | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.llm_gateway = llm_gateway
        self.personal_repository = personal_repository
        self.rendering_repository = rendering_repository

    def query_personal_knowledge(
        self,
        *,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext,
        model_profile: str,
        save: bool = False,
        provider: str | None = None,
        model: str | None = None,
    ) -> PersonalQueryAnswer:
        retrieval, bundle = self.orchestrator.build_query_bundle(
            domain=domain,
            question=question,
            scope_ref=scope_ref,
            profile_context=profile_context,
        )
        snapshot_ref = self._snapshot_ref(bundle, profile_context)
        request = {
            "messages": self._build_messages(bundle),
            "model_profile": model_profile,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
        }
        if provider is not None:
            request["provider"] = provider
        if model is not None:
            request["model"] = model

        generation = self.llm_gateway.generate_text(request)
        answer_markdown = self._normalize_answer_markdown(generation["content"], question)
        citations = self._build_citations(bundle)
        rationale_items = self._build_rationale_items(bundle)
        provenance = self._build_provenance(
            snapshot_ref=snapshot_ref,
            profile_context=profile_context,
            model_profile=model_profile,
            generation_metadata=generation["metadata"],
        )
        answer: PersonalQueryAnswer = {
            "answer_type": "personal_query_answer",
            "generation_strategy": self.generation_strategy,
            "question": question,
            "answer_summary": self._answer_summary(answer_markdown),
            "answer_rationale": self._answer_rationale(bundle),
            "answer_rationale_items": rationale_items,
            "answer_markdown": answer_markdown,
            "citations": citations,
            "personal_records_used": list(retrieval["personal_ids"]),
            "interpretation_records_used": list(retrieval["interpretation_ids"]),
            "fact_records_used": list(retrieval["fact_ids"]),
            "provenance": provenance,
            "input_bundle": bundle,
        }

        if save:
            self._save_answer_record(
                answer=answer,
                domain=domain,
                scope_ref=scope_ref,
                profile_context=profile_context,
                snapshot_ref=snapshot_ref,
            )
        return answer

    def _build_messages(self, bundle: PersonalQueryBundle) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You write user-scoped Personal answers for StrataWiki. "
                    "Use only the provided Personal, Interpretation, and Fact context. "
                    "Be explicit, practical, and do not invent unsupported claims."
                ),
            },
            {
                "role": "user",
                "content": self._render_prompt(bundle),
            },
        ]

    def _render_prompt(self, bundle: PersonalQueryBundle) -> str:
        sections = [
            f"Question:\n{bundle['question']}",
            f"Scope:\n{json.dumps(bundle['scope_ref'], ensure_ascii=True, sort_keys=True)}",
        ]
        profile_context = bundle.get("profile_context")
        if profile_context is not None:
            sections.append(
                "Profile Context:\n"
                + json.dumps(profile_context, ensure_ascii=True, sort_keys=True, indent=2)
            )
        snapshot_ref = bundle.get("snapshot_ref")
        if snapshot_ref is not None:
            sections.append(
                "Snapshot Ref:\n"
                + json.dumps(snapshot_ref, ensure_ascii=True, sort_keys=True, indent=2)
            )
        retrieval_metadata = bundle.get("retrieval_metadata")
        if retrieval_metadata is not None:
            sections.append(
                "Retrieval Metadata:\n"
                + json.dumps(retrieval_metadata, ensure_ascii=True, sort_keys=True, indent=2)
            )
        sections.append(
            self._render_context_section("Personal Context", bundle["personal_context"])
        )
        sections.append(
            self._render_context_section(
                "Interpretation Context",
                bundle["interpretation_context"],
            )
        )
        sections.append(self._render_context_section("Fact Context", bundle["fact_context"]))
        sections.append(
            "Write a markdown answer that is personalized to the profile, cites only the given context implicitly, "
            "and prioritizes concrete next steps."
        )
        return "\n\n".join(sections)

    def _render_context_section(
        self,
        title: str,
        items: list[PersonalQueryBundleItem],
    ) -> str:
        if not items:
            return f"{title}:\n- none"
        lines = [f"{title}:"]
        for item in items:
            line = f"- [{item['layer']}] {item['record_id']}: {item['title']} :: {item['summary']}"
            if "match_reason" in item:
                line += f" (match={item['match_reason']})"
            lines.append(line)
        return "\n".join(lines)

    def _normalize_answer_markdown(self, content: str, question: str) -> str:
        normalized = content.strip()
        if normalized:
            return normalized
        return f"## Answer\n\nNo answer content was generated for: {question}"

    def _build_citations(self, bundle: PersonalQueryBundle) -> list[PersonalQueryCitation]:
        citations: list[PersonalQueryCitation] = []
        seen: set[tuple[str, str]] = set()
        for items in (
            bundle["personal_context"],
            bundle["interpretation_context"],
            bundle["fact_context"],
        ):
            for item in items:
                key = (item["layer"], item["record_id"])
                if key in seen:
                    continue
                citations.append(
                    {
                        "layer": item["layer"],
                        "record_id": item["record_id"],
                        "title": item["title"],
                        "path": item.get("path"),
                    }
                )
                seen.add(key)
        return citations

    def _build_rationale_items(
        self,
        bundle: PersonalQueryBundle,
    ) -> list[PersonalQueryRationaleItem]:
        retrieval_metadata = bundle.get("retrieval_metadata", {})
        return [
            {
                "category": "selection",
                "summary": (
                    f"Selected {len(bundle['personal_context'])} personal, "
                    f"{len(bundle['interpretation_context'])} interpretation, and "
                    f"{len(bundle['fact_context'])} fact items."
                ),
            },
            {
                "category": "ranking",
                "summary": (
                    "Curated retrieval prioritized the default layer order "
                    f"{retrieval_metadata.get('layer_order', ['personal', 'interpretation', 'fact'])}."
                ),
            },
            {
                "category": "context",
                "summary": (
                    "Answer generation was bound to the retrieved snapshot tuple and profile version."
                ),
            },
        ]

    def _answer_summary(self, answer_markdown: str) -> str:
        text = re.sub(r"\s+", " ", answer_markdown.replace("#", " ")).strip()
        if len(text) <= 180:
            return text
        return text[:177].rstrip() + "..."

    def _answer_rationale(self, bundle: PersonalQueryBundle) -> str:
        retrieval_metadata = bundle.get("retrieval_metadata", {})
        return (
            "The answer was generated from curated retrieval across Personal, Interpretation, and Fact "
            f"using retrieval mode {retrieval_metadata.get('mode', 'curated')}."
        )

    def _snapshot_ref(
        self,
        bundle: PersonalQueryBundle,
        profile_context: ProfileContext,
    ) -> SnapshotRef:
        snapshot_ref = dict(bundle.get("snapshot_ref") or {})
        if "fact_snapshot_id" not in snapshot_ref:
            raise ValueError(
                "Personal query answers require a fact snapshot for provenance and persistence."
            )
        snapshot_ref["profile_version"] = profile_context["profile_version"]
        return snapshot_ref  # type: ignore[return-value]

    def _build_provenance(
        self,
        *,
        snapshot_ref: SnapshotRef,
        profile_context: ProfileContext,
        model_profile: str,
        generation_metadata: dict[str, str],
    ) -> PersonalQueryProvenance:
        provenance: PersonalQueryProvenance = {
            "fact_snapshot": snapshot_ref["fact_snapshot_id"],
            "profile_version": profile_context["profile_version"],
            "model_profile": model_profile,
            "prompt_id": generation_metadata["prompt_id"],
            "prompt_version": generation_metadata["prompt_version"],
            "provider": generation_metadata["provider"],
            "model": generation_metadata["model"],
        }
        if "interpretation_snapshot_id" in snapshot_ref:
            provenance["interpretation_snapshot"] = snapshot_ref["interpretation_snapshot_id"]
        return provenance

    def _save_answer_record(
        self,
        *,
        answer: PersonalQueryAnswer,
        domain: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext,
        snapshot_ref: SnapshotRef,
    ) -> str:
        if self.personal_repository is None or self.rendering_repository is None:
            raise ValueError(
                "Saving personal query answers requires both personal_repository and rendering_repository."
            )

        record_id = self._new_personal_record_id()
        body_path = self._body_path(
            scope_ref=scope_ref,
            question=answer["question"],
        )
        artifact: RenderedArtifact = {
            "domain": domain,
            "layer": "personal",
            "record_id": record_id,
            "path": body_path,
            "title": self._title_for_question(answer["question"]),
            "body_markdown": self._render_persisted_body(answer),
            "scope_ref": scope_ref,
            "snapshot_ref": snapshot_ref,
        }
        persisted_body_path = self.rendering_repository.write_artifact(artifact)
        self.personal_repository.save_record(
            {
                "id": record_id,
                "layer": "personal",
                "domain": domain,
                "kind": "query_answer",
                "title": artifact["title"],
                "summary": answer["answer_summary"],
                "scope_ref": scope_ref,
                "snapshot_ref": snapshot_ref,
                "profile_version": profile_context["profile_version"],
                "body_path": persisted_body_path,
                "status": "active",
                "schema_version": "personal.v1",
                "provenance": {
                    "upstream_versions": {
                        "fact_snapshot": snapshot_ref["fact_snapshot_id"],
                        "profile_version": profile_context["profile_version"],
                        **(
                            {
                                "interpretation_snapshot": snapshot_ref["interpretation_snapshot_id"]
                            }
                            if "interpretation_snapshot_id" in snapshot_ref
                            else {}
                        ),
                    },
                    "generated_by": {
                        "kind": "llm",
                        "provider": answer["provenance"]["provider"],
                        "model": answer["provenance"]["model"],
                        "prompt_version": answer["provenance"]["prompt_version"],
                    },
                    "generated_at": self._now_iso(),
                },
            }
        )
        return record_id

    def _render_persisted_body(self, answer: PersonalQueryAnswer) -> str:
        metadata = {
            "answer_type": answer["answer_type"],
            "question": answer["question"],
            "anchors": answer["interpretation_records_used"] + answer["fact_records_used"],
            "anchor_details": [
                {
                    "layer": citation["layer"],
                    "id": citation["record_id"],
                    "title": citation["title"],
                }
                for citation in answer["citations"]
                if citation["layer"] in {"interpretation", "fact"}
            ],
            "provenance": answer["provenance"],
        }
        return (
            "<!-- stratawiki:personal_query_answer\n"
            + json.dumps(metadata, ensure_ascii=True, indent=2, sort_keys=True)
            + "\n-->\n\n"
            + answer["answer_markdown"].rstrip()
            + "\n"
        )

    def _title_for_question(self, question: str) -> str:
        normalized = question.strip().rstrip("?")
        return normalized or "Personal query answer"

    def _body_path(self, *, scope_ref: ScopeRef, question: str) -> str:
        slug = self._slug(question) or "personal-query-answer"
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        return (
            f"wiki/users/{scope_ref['user_id']}/answers/"
            f"{timestamp}-{slug}.md"
        )

    def _new_personal_record_id(self) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"personal:query_answer:{timestamp}:{uuid4().hex[:8]}"

    def _slug(self, text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug[:80]

    def _now_iso(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
