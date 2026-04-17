from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from wiki_mcp.adapters.llm.gateway import LLMGateway
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
    ) -> None:
        self.llm_gateway = llm_gateway
        self.model_profile = model_profile
        self.provider = provider
        self.model = model
        self.freshness_ttl = freshness_ttl

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
        evidence = self._build_evidence(context)
        confidence = self._compute_confidence(evidence_count=len(evidence))

        return {
            "id": self._new_record_id(context),
            "family": self.family,
            "kind": str(output.get("kind") or "market_trend"),
            "title": str(output.get("title") or f"Market trend for {context.subject_id}"),
            "claim": str(output.get("claim") or "").strip(),
            "summary": str(output.get("summary") or "").strip(),
            "confidence": confidence,
            "computed_at": computed_at,
            "expires_at": self._compute_expires_at(computed_at),
            "body": self._build_body(output),
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
                    "content": (
                        "You synthesize one evidence-backed recruiting market trend. "
                        "Return concise structured output grounded only in the provided facts."
                    ),
                },
                {
                    "role": "user",
                    "content": self._facts_prompt(context),
                },
            ],
            "model_profile": self.model_profile,
            "prompt_id": "interp.market_trend",
            "prompt_version": "interp.market_trend.v1",
            "schema_name": "interpretation.market_trend",
            "schema_version": "interpretation.market_trend.v1",
            "output_schema": {
                "type": "object",
                "required": ["title", "claim", "summary", "body"],
                "properties": {
                    "kind": {"type": "string"},
                    "title": {"type": "string"},
                    "claim": {"type": "string"},
                    "summary": {"type": "string"},
                    "body": {
                        "type": "object",
                        "required": ["signals", "observations", "counterpoints"],
                        "properties": {
                            "headline": {"type": "string"},
                            "thesis": {"type": "string"},
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

        return "\n".join(
            [
                f"Domain: {context.domain}",
                f"Family: {context.family}",
                f"Subject type: {context.subject_type}",
                f"Subject id: {context.subject_id}",
                "Facts:",
                *fact_lines,
            ]
        )

    def _build_body(self, output: dict[str, object]) -> dict[str, object]:
        raw_body = output.get("body")
        if not isinstance(raw_body, dict):
            return {
                "headline": "",
                "thesis": "",
                "signals": [],
                "observations": [],
                "counterpoints": [],
            }
        return {
            "headline": str(raw_body.get("headline") or "").strip(),
            "thesis": str(raw_body.get("thesis") or output.get("claim") or "").strip(),
            "signals": self._string_list(raw_body.get("signals")),
            "observations": self._string_list(raw_body.get("observations")),
            "counterpoints": self._string_list(raw_body.get("counterpoints")),
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
