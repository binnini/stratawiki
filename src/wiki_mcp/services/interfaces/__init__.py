"""Service-layer interfaces and protocols."""

from wiki_mcp.services.interfaces.core_ingestion import CoreIngestionService
from wiki_mcp.services.interfaces.dependency import DependencyService
from wiki_mcp.services.interfaces.domain_ingestion import DomainIngestionPlugin
from wiki_mcp.services.interfaces.page_reads import PageReadService
from wiki_mcp.services.interfaces.profile_context import ProfileContextService
from wiki_mcp.services.interfaces.rendering import RenderingService
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
    "DependencyService",
    "DomainIngestionPlugin",
    "FactRepository",
    "InterpretationRepository",
    "OutboxRepository",
    "PageReadService",
    "PersonalRepository",
    "ProfileContextRepository",
    "ProfileContextService",
    "RenderingRepository",
    "RenderingService",
    "RetrievalService",
    "SnapshotRepository",
]
