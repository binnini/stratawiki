from __future__ import annotations

from typing import TypedDict

from wiki_mcp.schemas.personal_query_bundle import PersonalQueryBundle


class PersonalQueryCitation(TypedDict):
    """One citation emitted with a synthesized personal answer."""

    layer: str
    record_id: str
    title: str
    path: str | None


class PersonalQueryAnswer(TypedDict):
    """Deterministic answer payload for the first personal query slice."""

    question: str
    answer_summary: str
    answer_markdown: str
    citations: list[PersonalQueryCitation]
    input_bundle: PersonalQueryBundle
