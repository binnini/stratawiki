from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from wiki_mcp.schemas.personal_query_bundle import PersonalQueryBundle


class PersonalQueryCitation(TypedDict):
    """One citation emitted with a synthesized personal answer."""

    layer: str
    record_id: str
    title: str
    path: str | None


class PersonalQueryRationaleItem(TypedDict):
    """Structured rationale entry emitted with a personal answer."""

    category: Literal["selection", "ranking", "context"]
    summary: str


class PersonalQueryProvenance(TypedDict):
    """Minimal provenance tuple returned with personal query answers."""

    fact_snapshot: str
    interpretation_snapshot: NotRequired[str]
    profile_version: NotRequired[str]
    model_profile: str
    prompt_id: str
    prompt_version: str
    provider: str
    model: str


class PersonalQueryAnswer(TypedDict):
    """Deterministic answer payload for the first personal query slice."""

    answer_type: Literal["personal_query_answer"]
    generation_strategy: Literal["deterministic_summary_bundle_v1", "curated_retrieval_llm_v1"]
    personal_family: NotRequired[str]
    question: str
    answer_summary: str
    answer_rationale: str
    answer_rationale_items: list[PersonalQueryRationaleItem]
    answer_markdown: str
    recommended_actions: NotRequired[list[str]]
    citations: list[PersonalQueryCitation]
    personal_records_used: list[str]
    interpretation_records_used: list[str]
    fact_records_used: list[str]
    provenance: PersonalQueryProvenance
    input_bundle: PersonalQueryBundle
