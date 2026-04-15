"""Shared schema definitions."""

from wiki_mcp.schemas.dependency_impact import DependencyImpact
from wiki_mcp.schemas.external_recruiting_payload import (
    RecruitingAttachmentPayload,
    RecruitingCompanyCoordinates,
    RecruitingCompanyPayload,
    RecruitingJobPayload,
    RecruitingJobPostingPayload,
    RecruitingRecruitmentSectionPayload,
    RecruitingSelectionStepPayload,
    RecruitingSourcePayload,
    RecruitingSourceProvenance,
)
from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.fact_write_result import FactWriteResult
from wiki_mcp.schemas.ingestion_batch import IngestionBatch
from wiki_mcp.schemas.ingestion_error import IngestionError
from wiki_mcp.schemas.ingestion_execution_result import IngestionExecutionResult
from wiki_mcp.schemas.ingestion_result import IngestionResult
from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.outbox_event import OutboxEvent
from wiki_mcp.schemas.personal_record import PersonalRecord
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.retrieval_result import RetrievalResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.schemas.validation_result import ValidationResult

__all__ = [
    "DependencyImpact",
    "FactRecord",
    "FactRelation",
    "FactWriteResult",
    "IngestionBatch",
    "IngestionError",
    "IngestionExecutionResult",
    "IngestionResult",
    "InterpretationRecord",
    "OutboxEvent",
    "PersonalRecord",
    "ProfileContext",
    "RecruitingAttachmentPayload",
    "RecruitingCompanyCoordinates",
    "RecruitingCompanyPayload",
    "RecruitingJobPayload",
    "RecruitingJobPostingPayload",
    "RecruitingRecruitmentSectionPayload",
    "RecruitingSelectionStepPayload",
    "RecruitingSourcePayload",
    "RecruitingSourceProvenance",
    "RenderedArtifact",
    "RetrievalResult",
    "ScopeRef",
    "SnapshotRef",
    "SourceRecord",
    "ValidationResult",
]
