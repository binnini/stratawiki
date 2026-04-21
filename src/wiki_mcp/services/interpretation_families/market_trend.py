from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from wiki_mcp.adapters.llm.gateway import LLMGateway, LLMGatewayError
from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.prompts import PromptCatalog, resolve_prompt_language, resolve_prompt_version
from wiki_mcp.services.interpretation_families.base import InterpretationProposalContext


class MarketTrendInterpretationBuilder:
    """LLM-backed builder for the first published market_trend family slice."""

    family = "market_trend"

    def __init__(
        self,
        *,
        llm_gateway: LLMGateway,
        model_profile: str = "deep_synthesis",
        provider: str | None = None,
        model: str | None = None,
        freshness_ttl: timedelta = timedelta(hours=24),
        prompt_catalog: PromptCatalog | None = None,
    ) -> None:
        self.llm_gateway = llm_gateway
        self.model_profile = model_profile
        self.provider = provider
        self.model = model
        self.freshness_ttl = freshness_ttl
        self.prompt_catalog = prompt_catalog or PromptCatalog(
            language=resolve_prompt_language()
        )

    def build_proposal(
        self,
        context: InterpretationProposalContext,
    ) -> dict[str, object] | None:
        if context.family != self.family or not context.facts:
            return None

        computed_at = self._resolve_computed_at(context)
        llm_output = self.llm_gateway.generate_structured(
            self._build_request(context)
        )
        output = llm_output["output"]
        body = self._build_body(output, context)
        title = self._resolve_required_text(
            output.get("title"),
            fallback_values=[
                output.get("claim"),
                output.get("summary"),
                body.get("headline"),
                body.get("thesis"),
                self._fallback_title(context),
            ],
        )
        claim = self._resolve_required_text(
            output.get("claim"),
            fallback_values=[
                output.get("summary"),
                body.get("thesis"),
                body.get("headline"),
                self._fallback_claim(context),
            ],
        )
        summary = self._resolve_required_text(
            output.get("summary"),
            fallback_values=[
                self._fallback_summary(context),
                output.get("claim"),
                body.get("thesis"),
                body.get("headline"),
            ],
        )
        evidence = self._build_evidence(context)
        confidence = self._compute_confidence(evidence_count=len(evidence))

        return {
            "id": self._new_record_id(context),
            "family": self.family,
            "kind": str(output.get("kind") or "market_trend"),
            "title": title,
            "claim": claim,
            "summary": summary,
            "confidence": confidence,
            "computed_at": computed_at,
            "expires_at": self._compute_expires_at(computed_at),
            "body": body,
            "evidence": evidence,
            "provenance": {
                **dict(context.provenance),
                "generated_by": {
                    **dict(context.provenance.get("generated_by", {})),
                    **llm_output["metadata"],
                },
                "generated_at": computed_at,
            },
            "render_hints": {
                "page_family": self.family,
                "page_key": context.subject_id,
                "priority": "high" if confidence >= 0.8 else "medium",
            },
        }

    def _build_request(
        self,
        context: InterpretationProposalContext,
    ) -> dict[str, object]:
        request: dict[str, object] = {
            "messages": [
                {
                    "role": "system",
                    "content": self.prompt_catalog.read_text(
                        "interpretation_market_trend",
                        "system",
                    ),
                },
                {
                    "role": "user",
                    "content": self._facts_prompt(context),
                },
            ],
            "model_profile": self.model_profile,
            "prompt_id": "interp.market_trend",
            "prompt_version": resolve_prompt_version(
                "interp.market_trend.v1",
                self.prompt_catalog.language,
            ),
            "schema_name": "interpretation.market_trend",
            "schema_version": "interpretation.market_trend.v1",
            "output_schema": {
                "type": "object",
                "required": ["title", "claim", "summary", "body"],
                "properties": {
                    "kind": {"type": "string"},
                    "title": {"type": "string", "minLength": 8},
                    "claim": {"type": "string", "minLength": 12},
                    "summary": {"type": "string", "minLength": 12},
                    "body": {
                        "type": "object",
                        "required": ["signals", "observations", "counterpoints"],
                        "properties": {
                            "headline": {"type": "string", "minLength": 8},
                            "thesis": {"type": "string", "minLength": 12},
                            "signals": {"type": "array", "items": {"type": "string"}},
                            "observations": {"type": "array", "items": {"type": "string"}},
                            "counterpoints": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        }
        if self.provider is not None:
            request["provider"] = self.provider
        if self.model is not None:
            request["model"] = self.model
        return request

    def _facts_prompt(
        self,
        context: InterpretationProposalContext,
    ) -> str:
        fact_lines: list[str] = []
        for fact in context.facts[:8]:
            attributes = fact.get("attributes", {})
            title = ""
            summary = ""
            if isinstance(attributes, dict):
                raw_title = attributes.get("title") or attributes.get("name") or attributes.get("label")
                raw_summary = attributes.get("summary") or attributes.get("description")
                title = str(raw_title).strip() if raw_title else ""
                summary = str(raw_summary).strip() if raw_summary else ""
            line = f"- {fact['id']}: {fact['entity_type']}"
            if title:
                line += f" | title={title}"
            if summary:
                line += f" | summary={summary}"
            fact_lines.append(line)

        return self.prompt_catalog.render(
            "interpretation_market_trend",
            "user",
            domain=context.domain,
            family=context.family,
            subject_type=context.subject_type,
            subject_id=context.subject_id,
            facts_block="\n".join(fact_lines),
        )

    def _build_body(
        self,
        output: dict[str, object],
        context: InterpretationProposalContext,
    ) -> dict[str, object]:
        raw_body = output.get("body")
        if not isinstance(raw_body, dict):
            raw_body = {}
        fallback_body = self._fallback_body(context)
        return {
            "headline": self._resolve_required_text(
                raw_body.get("headline"),
                fallback_values=[
                    raw_body.get("thesis"),
                    output.get("title"),
                    output.get("claim"),
                    fallback_body["headline"],
                ],
            ),
            "thesis": self._resolve_required_text(
                raw_body.get("thesis"),
                fallback_values=[
                    output.get("claim"),
                    output.get("summary"),
                    raw_body.get("headline"),
                    fallback_body["thesis"],
                ],
            ),
            "signals": self._string_list(raw_body.get("signals")) or fallback_body["signals"],
            "observations": self._string_list(raw_body.get("observations")) or fallback_body["observations"],
            "counterpoints": self._string_list(raw_body.get("counterpoints")) or fallback_body["counterpoints"],
        }

    def _build_evidence(
        self,
        context: InterpretationProposalContext,
    ) -> list[dict[str, object]]:
        capped_facts = context.facts[:5]
        weight = round(1 / len(capped_facts), 2)
        evidence: list[dict[str, object]] = []
        for index, fact in enumerate(capped_facts):
            evidence.append(
                {
                    "fact_id": fact["id"],
                    "weight": weight,
                    "role": "primary" if index == 0 else "supporting",
                }
            )
        return evidence

    def _compute_confidence(self, *, evidence_count: int) -> float:
        return round(min(0.9, 0.55 + evidence_count * 0.07), 2)

    def _resolve_computed_at(self, context: InterpretationProposalContext) -> str:
        generated_at = context.provenance.get("generated_at")
        if isinstance(generated_at, str) and generated_at.strip():
            return generated_at
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _compute_expires_at(self, computed_at: str) -> str:
        computed = datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
        return (computed + self.freshness_ttl).isoformat().replace("+00:00", "Z")

    def _new_record_id(self, context: InterpretationProposalContext) -> str:
        return f"interp:proposal:{self.family}:{context.subject_id}:{uuid4().hex[:8]}"

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _resolve_required_text(
        self,
        value: object,
        *,
        fallback_values: list[object],
    ) -> str:
        for candidate in [value, *fallback_values]:
            normalized = str(candidate or "").strip()
            if normalized:
                return normalized
        raise LLMGatewayError(
            "LLM_INVALID_SCHEMA_RESPONSE",
            "Market trend structured generation returned empty required text fields.",
            retryable=True,
        )

    def _fallback_title(self, context: InterpretationProposalContext) -> str:
        return f"Evidence-backed market trend for {context.subject_id}"

    def _fallback_claim(self, context: InterpretationProposalContext) -> str:
        emphasis = self._primary_fact_phrase(context.facts)
        if emphasis:
            return (
                f"Recent recruiting facts for {context.subject_id} repeatedly highlight {emphasis}, "
                "suggesting a coherent market trend in this segment."
            )
        return (
            f"Recent recruiting facts for {context.subject_id} show a repeated hiring signal across "
            f"{len(context.facts)} supporting records."
        )

    def _fallback_summary(self, context: InterpretationProposalContext) -> str:
        return (
            f"Multiple recruiting facts in {context.subject_id} point to a repeatable market signal "
            "worth tracking."
        )

    def _fallback_body(self, context: InterpretationProposalContext) -> dict[str, object]:
        evidence_lines = self._fact_signal_lines(context.facts)
        headline = self._fallback_title(context)
        thesis = self._fallback_claim(context)
        return {
            "headline": headline,
            "thesis": thesis,
            "signals": evidence_lines[:3],
            "observations": [
                f"Supporting fact records available: {len(context.facts)}.",
                f"Primary segment under review: {context.subject_id}.",
            ],
            "counterpoints": [
                "This fallback interpretation should be reviewed because the model output was incomplete."
            ],
        }

    def _primary_fact_phrase(self, facts: list[FactRecord]) -> str:
        for fact in facts:
            attributes = fact.get("attributes", {})
            if isinstance(attributes, dict):
                for key in ("summary", "title", "name", "label", "description"):
                    value = str(attributes.get(key) or "").strip()
                    if value:
                        return value.rstrip(".")
        return ""

    def _fact_signal_lines(self, facts: list[FactRecord]) -> list[str]:
        lines: list[str] = []
        for fact in facts[:3]:
            attributes = fact.get("attributes", {})
            if isinstance(attributes, dict):
                title = str(attributes.get("title") or attributes.get("name") or "").strip()
                summary = str(attributes.get("summary") or attributes.get("description") or "").strip()
                text = summary or title
                if text:
                    lines.append(text)
                    continue
            lines.append(f"Observed {fact['entity_type']} signal from {fact['canonical_key']}.")
        return lines
