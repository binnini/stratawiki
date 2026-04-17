"""Source connector adapters."""

from wiki_mcp.adapters.sources.worknet import (
    WorknetRecruitingExternalAdapter,
    WorknetRecruitingSourceProvider,
)

__all__ = [
    "WorknetRecruitingExternalAdapter",
    "WorknetRecruitingSourceProvider",
]
