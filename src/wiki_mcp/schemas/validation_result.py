from __future__ import annotations

from typing import TypedDict


class ValidationResult(TypedDict):
    """Structured validation result returned by ingestion plugins."""

    ok: bool
    warnings: list[str]
    errors: list[str]
