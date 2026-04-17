from __future__ import annotations

from typing import NotRequired, TypedDict


class SnapshotRef(TypedDict):
    """Snapshot tuple used to explain and reproduce derived outputs."""

    fact_snapshot_id: str
    interpretation_snapshot_id: NotRequired[str]
    profile_version: NotRequired[str]
    personal_snapshot_id: NotRequired[str]
