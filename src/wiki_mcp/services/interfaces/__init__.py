"""Service-layer interfaces and protocols available in the current migration slice."""

from wiki_mcp.services.interfaces.repositories import (
    DependencyRepository,
    FactRepository,
    InterpretationRepository,
    OutboxRepository,
    PersonalRepository,
    ProfileContextRepository,
    RenderingRepository,
    SnapshotRepository,
)
from wiki_mcp.services.interfaces.retrieval import RetrievalService

__all__ = [
    "DependencyRepository",
    "FactRepository",
    "InterpretationRepository",
    "OutboxRepository",
    "PersonalRepository",
    "ProfileContextRepository",
    "RenderingRepository",
    "RetrievalService",
    "SnapshotRepository",
]
