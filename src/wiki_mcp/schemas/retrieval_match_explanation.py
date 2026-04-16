from __future__ import annotations

from typing import Literal, TypedDict


class RetrievalMatchExplanation(TypedDict):
    """Retrieval-owned explanation for one matched candidate."""

    layer: Literal["personal", "interpretation", "fact"]
    record_id: str
    score: int
    match_type: str
    matched_fields: list[str]
    profile_boost_applied: bool
