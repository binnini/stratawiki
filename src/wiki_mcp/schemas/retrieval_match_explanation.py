from __future__ import annotations

from typing import Literal, TypedDict


class RetrievalMatchExplanation(TypedDict):
    """Retrieval-owned explanation for one matched candidate."""

    layer: Literal["personal", "interpretation", "fact"]
    record_id: str
    rank: int
    score: int
    match_type: str
    matched_fields: list[str]
    matched_token_count: int
    profile_boost_applied: bool
