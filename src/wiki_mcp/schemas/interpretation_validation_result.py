from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from wiki_mcp.schemas.interpretation_lifecycle import InterpretationLifecycleStatus


class InterpretationValidationError(TypedDict):
    """Structured validation error for proposal review and promotion."""

    code: str
    message: str
    field: NotRequired[str]
    details: NotRequired[dict[str, Any]]


class InterpretationValidationResult(TypedDict):
    """Program-side validation result for one interpretation proposal."""

    ok: bool
    record_id: str
    status: InterpretationLifecycleStatus
    errors: list[InterpretationValidationError]
    warnings: list[str]
