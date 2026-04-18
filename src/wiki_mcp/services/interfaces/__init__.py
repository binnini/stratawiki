"""Service-layer interfaces and protocols available in the current migration slice."""

from wiki_mcp.services.interfaces.core_ingestion import CoreIngestionService
from wiki_mcp.services.interfaces.domain_pack_registry import DomainPackRegistry
from wiki_mcp.services.interfaces.domain_ingestion import DomainIngestionPlugin
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
    "CoreIngestionService",
    "DependencyRepository",
    "DomainPackRegistry",
    "DomainIngestionPlugin",
    "FactRepository",
    "InterpretationRepository",
    "OutboxRepository",
    "PersonalRepository",
    "ProfileContextRepository",
    "RenderingRepository",
    "RetrievalService",
    "SnapshotRepository",
]
