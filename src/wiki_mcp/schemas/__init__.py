"""Schema exports available in the current migration slice."""

from wiki_mcp.schemas.dependency_impact import DependencyImpact
from wiki_mcp.schemas.dependency_edge import DependencyEdge
from wiki_mcp.schemas.domain_pack import (
    AttributeDefinition,
    CompositeIdentityRule,
    DomainPack,
    DomainPackCompatibility,
    DomainPackManifest,
    DomainPackOwner,
    EntityTypeDefinition,
    ExternalIdIdentityRule,
    IdentityRule,
    MergePolicy,
    ProjectionHints,
    RelationTypeDefinition,
)
from wiki_mcp.schemas.domain_pack_review import (
    DomainPackApprovalReport,
    DomainPackCompatibilityDecision,
    DomainPackCompatibilityIssue,
    DomainPackCompatibilityReport,
    DomainPackRegistrationError,
    DomainPackReviewAudit,
    DomainPackValidationIssue,
    DomainPackValidationReport,
)
from wiki_mcp.schemas.domain_proposal import (
    DomainProposalAudit,
    DomainProposalBatch,
    DomainProposalFactDecision,
    DomainProposalIngestionResult,
    DomainProposalRelationDecision,
    DomainProposalRejection,
    DomainProposalWritePlan,
    FactProposal,
    ProposalEntityRef,
    ProposalEvidenceRef,
    ProposalIdentityHints,
    RelationProposal,
)
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
from wiki_mcp.schemas.interpretation_lifecycle import (
    INTERPRETATION_LIFECYCLE_STATUSES,
    INTERPRETATION_STATUS_DELETED,
    INTERPRETATION_STATUS_PROPOSED,
    INTERPRETATION_STATUS_PUBLISHED,
    INTERPRETATION_STATUS_REJECTED,
    INTERPRETATION_STATUS_STALE,
    INTERPRETATION_STATUS_SUPERSEDED,
    INTERPRETATION_STATUS_VALIDATED,
    InterpretationLifecycleStatus,
)
from wiki_mcp.schemas.interpretation_record import (
    InterpretationRecord,
    interpretation_payload,
    interpretation_support_links,
    materialize_interpretation_record,
)
from wiki_mcp.schemas.interpretation_validation_result import (
    InterpretationValidationError,
    InterpretationValidationResult,
)
from wiki_mcp.schemas.outbox_event import (
    FactIngestedPayload,
    InterpretationSnapshotBuildRequestedPayload,
    InterpretationSnapshotPublishedPayload,
    OutboxEvent,
    OutboxEventRecord,
    PersonalRecordsMarkedStalePayload,
    PersonalRecordsRegeneratedPayload,
)
from wiki_mcp.schemas.personal_anchor import PersonalAnchor
from wiki_mcp.schemas.personal_record import PersonalRecord
from wiki_mcp.schemas.personal_query_answer import (
    PersonalQueryAnswer,
    PersonalQueryCitation,
    PersonalQueryProvenance,
    PersonalQueryRationaleItem,
)
from wiki_mcp.schemas.personal_query_bundle import (
    PersonalQueryBundle,
    PersonalQueryBundleItem,
)
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.provenance import GeneratedBy, GeneratedByKind, Provenance
from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.rendered_page import RenderedPage
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.retrieval_fact_summary import RetrievalFactSummary
from wiki_mcp.schemas.retrieval_interpretation_summary import (
    RetrievalInterpretationSummary,
)
from wiki_mcp.schemas.retrieval_match_explanation import RetrievalMatchExplanation
from wiki_mcp.schemas.retrieval_metadata import RetrievalMetadata
from wiki_mcp.schemas.retrieval_personal_summary import RetrievalPersonalSummary
from wiki_mcp.schemas.retrieval_result import RetrievalResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.schemas.validation_result import ValidationResult

__all__ = [
    "DependencyImpact",
    "DependencyEdge",
    "AttributeDefinition",
    "CompositeIdentityRule",
    "DomainPack",
    "DomainPackApprovalReport",
    "DomainPackCompatibility",
    "DomainPackCompatibilityDecision",
    "DomainPackCompatibilityIssue",
    "DomainPackCompatibilityReport",
    "DomainPackManifest",
    "DomainPackOwner",
    "DomainPackRegistrationError",
    "DomainPackReviewAudit",
    "DomainPackValidationIssue",
    "DomainPackValidationReport",
    "DomainProposalAudit",
    "DomainProposalBatch",
    "DomainProposalFactDecision",
    "DomainProposalIngestionResult",
    "DomainProposalRelationDecision",
    "DomainProposalRejection",
    "DomainProposalWritePlan",
    "EntityTypeDefinition",
    "ExternalIdIdentityRule",
    "FactProposal",
    "FactIngestedPayload",
    "FactRecord",
    "FactRelation",
    "FactWriteResult",
    "IngestionBatch",
    "IngestionError",
    "IngestionExecutionResult",
    "IngestionResult",
    "INTERPRETATION_LIFECYCLE_STATUSES",
    "INTERPRETATION_STATUS_DELETED",
    "INTERPRETATION_STATUS_PROPOSED",
    "INTERPRETATION_STATUS_PUBLISHED",
    "INTERPRETATION_STATUS_REJECTED",
    "INTERPRETATION_STATUS_STALE",
    "INTERPRETATION_STATUS_SUPERSEDED",
    "INTERPRETATION_STATUS_VALIDATED",
    "IdentityRule",
    "InterpretationRecord",
    "InterpretationValidationError",
    "InterpretationValidationResult",
    "InterpretationLifecycleStatus",
    "interpretation_payload",
    "interpretation_support_links",
    "materialize_interpretation_record",
    "InterpretationSnapshotBuildRequestedPayload",
    "InterpretationSnapshotPublishedPayload",
    "OutboxEvent",
    "OutboxEventRecord",
    "PersonalAnchor",
    "PersonalRecordsMarkedStalePayload",
    "PersonalRecordsRegeneratedPayload",
    "PersonalRecord",
    "PersonalQueryAnswer",
    "PersonalQueryBundle",
    "PersonalQueryBundleItem",
    "PersonalQueryCitation",
    "PersonalQueryProvenance",
    "PersonalQueryRationaleItem",
    "MergePolicy",
    "ProjectionHints",
    "ProposalEntityRef",
    "ProposalEvidenceRef",
    "ProposalIdentityHints",
    "ProfileContext",
    "GeneratedBy",
    "GeneratedByKind",
    "Provenance",
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
    "RenderedPage",
    "RenderedPageSummary",
    "RelationTypeDefinition",
    "RelationProposal",
    "RetrievalFactSummary",
    "RetrievalInterpretationSummary",
    "RetrievalMatchExplanation",
    "RetrievalMetadata",
    "RetrievalPersonalSummary",
    "RetrievalResult",
    "ScopeRef",
    "SnapshotRef",
    "SourceRecord",
    "ValidationResult",
]
