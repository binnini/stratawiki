from __future__ import annotations

from typing import NotRequired, TypedDict


class RetrievalInterpretationSummary(TypedDict):
    """Retrieval-facing summary of a canonical Interpretation record."""

    id: str
    domain: str
    kind: str
    subject_type: str
    subject_id: str
    status: str
    confidence: float
    summary: NotRequired[str]
