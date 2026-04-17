from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


GeneratedByKind = Literal["llm", "program", "user", "operator", "system"]


class GeneratedBy(TypedDict):
    """Shared generator metadata for derived records."""

    kind: GeneratedByKind
    provider: NotRequired[str]
    model: NotRequired[str]
    prompt_version: NotRequired[str]


class Provenance(TypedDict):
    """Shared provenance envelope for canonical and derived records."""

    source_ids: NotRequired[list[str]]
    upstream_versions: NotRequired[dict[str, str]]
    generated_by: NotRequired[GeneratedBy]
    generated_at: NotRequired[str]
    notes: NotRequired[list[str]]
