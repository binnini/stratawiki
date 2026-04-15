from __future__ import annotations

from typing import TypedDict


class DependencyImpact(TypedDict):
    """Downstream impact summary for a changed record."""

    affected_interpretation_ids: list[str]
    affected_rendered_paths: list[str]
    affected_personal_ids: list[str]
