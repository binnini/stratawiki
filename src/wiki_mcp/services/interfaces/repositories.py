from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.dependency_edge import DependencyEdge
from wiki_mcp.schemas.dependency_impact import DependencyImpact
from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.fact_write_result import FactWriteResult
from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.outbox_event import OutboxEvent, OutboxEventRecord
from wiki_mcp.schemas.personal_record import PersonalRecord
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.rendered_page import RenderedPage
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class FactRepository(Protocol):
    """Persistence boundary for canonical Fact records and relations."""

    def get_by_canonical_keys(
        self,
        canonical_keys: list[str],
        scope_ref: ScopeRef,
    ) -> list[FactRecord]:
        """Load canonical Fact records by canonical key with scope filtering."""

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: ScopeRef,
    ) -> list[FactRecord]:
        """Load Fact records by id with scope filtering."""

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[FactRecord]:
        """Search Fact records as bounded retrieval candidates."""

    def write_facts(
        self,
        records: list[FactRecord],
        relations: list[FactRelation],
        *,
        fact_snapshot_id: str,
    ) -> FactWriteResult:
        """Persist canonical Fact records and explicit relations."""


class InterpretationRepository(Protocol):
    """Persistence boundary for canonical shared Interpretation records."""

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: ScopeRef,
    ) -> list[InterpretationRecord]:
        """Load interpretation records by id with scope filtering."""

    def list_records(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        family: str | None = None,
        kind: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 20,
    ) -> list[InterpretationRecord]:
        """List interpretation records for exact partition or lifecycle filters."""

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[InterpretationRecord]:
        """Search Interpretation records as bounded retrieval candidates."""

    def save_records(
        self,
        records: list[InterpretationRecord],
        snapshot_ref: SnapshotRef,
    ) -> list[str]:
        """Persist interpretation records and return stored ids."""


class PersonalRepository(Protocol):
    """Persistence boundary for user-scoped Personal metadata."""

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: ScopeRef,
    ) -> list[PersonalRecord]:
        """Load personal records by id with scope filtering."""

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[PersonalRecord]:
        """Search Personal records as bounded retrieval candidates."""

    def search_by_anchors(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        interpretation_ids: list[str],
        fact_ids: list[str],
        limit: int,
    ) -> list[PersonalRecord]:
        """Search Personal records by persisted anchor targets."""

    def save_record(self, record: PersonalRecord) -> str:
        """Persist one Personal metadata record and return its id."""


class ProfileContextRepository(Protocol):
    """Persistence boundary for profile and user context state."""

    def get_profile_context(
        self,
        domain: str,
        tenant_id: str,
        user_id: str,
    ) -> ProfileContext:
        """Return the current persisted profile context."""

    def save_profile_context(self, profile: ProfileContext) -> None:
        """Persist or update one profile context."""


class RenderingRepository(Protocol):
    """Persistence boundary for readable rendered artifacts."""

    def write_artifact(self, artifact: RenderedArtifact) -> str:
        """Persist one rendered artifact and return its path."""

    def read_body(
        self,
        *,
        path: str,
        scope_ref: ScopeRef,
    ) -> str | None:
        """Read one rendered artifact body by path with scope filtering."""

    def get_page(
        self,
        *,
        domain: str,
        layer: str,
        record_id: str,
        scope_ref: ScopeRef,
    ) -> RenderedPage | None:
        """Load one rendered page with scope filtering."""

    def list_pages(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        layer: str | None = None,
        limit: int = 20,
    ) -> list[RenderedPageSummary]:
        """List rendered page metadata in recency order with scope filtering."""


class SnapshotRepository(Protocol):
    """Persistence boundary for snapshot publication and lookup."""

    def publish_snapshot(
        self,
        layer: str,
        domain: str,
        snapshot_ref: SnapshotRef,
    ) -> str:
        """Publish the current snapshot pointer for a layer or partition."""

    def get_snapshot_status(
        self,
        *,
        layer: str | None = None,
        domain: str,
    ) -> dict[str, object] | None:
        """Return the current published snapshot status for a domain or one layer."""


class OutboxRepository(Protocol):
    """Persistence boundary for asynchronous projection events."""

    def append_events(self, events: list[OutboxEvent]) -> list[str]:
        """Append outbox events and return stored event ids."""

    def claim_pending(
        self,
        *,
        limit: int,
        event_types: list[str] | None = None,
    ) -> list[OutboxEventRecord]:
        """Claim pending outbox events for processing."""

    def mark_processed(self, event_id: str) -> None:
        """Mark a claimed outbox event as processed."""

    def mark_failed(
        self,
        event_id: str,
        error_message: str,
        *,
        retryable: bool = True,
    ) -> None:
        """Requeue or terminally fail a claimed outbox event."""


class DependencyRepository(Protocol):
    """Persistence boundary for dependency and impact lookup."""

    def replace_edges_for_target(
        self,
        *,
        domain: str,
        to_layer: str,
        to_id: str,
        scope_ref: ScopeRef,
        edges: list[DependencyEdge],
    ) -> None:
        """Replace downstream dependency edges for one target record."""

    def get_impact(
        self,
        domain: str,
        layer: str,
        record_id: str,
        scope_ref: ScopeRef,
    ) -> DependencyImpact:
        """Return downstream dependency impact for a changed record."""
