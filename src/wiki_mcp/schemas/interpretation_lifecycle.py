from __future__ import annotations

from typing import Final, Literal


INTERPRETATION_STATUS_PROPOSED: Final = "proposed"
INTERPRETATION_STATUS_VALIDATED: Final = "validated"
INTERPRETATION_STATUS_PUBLISHED: Final = "published"
INTERPRETATION_STATUS_STALE: Final = "stale"
INTERPRETATION_STATUS_SUPERSEDED: Final = "superseded"
INTERPRETATION_STATUS_REJECTED: Final = "rejected"
INTERPRETATION_STATUS_DELETED: Final = "deleted"

INTERPRETATION_LIFECYCLE_STATUSES: Final[tuple[str, ...]] = (
    INTERPRETATION_STATUS_PROPOSED,
    INTERPRETATION_STATUS_VALIDATED,
    INTERPRETATION_STATUS_PUBLISHED,
    INTERPRETATION_STATUS_STALE,
    INTERPRETATION_STATUS_SUPERSEDED,
    INTERPRETATION_STATUS_REJECTED,
    INTERPRETATION_STATUS_DELETED,
)

InterpretationLifecycleStatus = Literal[
    "proposed",
    "validated",
    "published",
    "stale",
    "superseded",
    "rejected",
    "deleted",
]
