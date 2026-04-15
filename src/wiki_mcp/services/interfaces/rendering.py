from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.schemas.scope_ref import ScopeRef


class RenderingService(Protocol):
    """Rendering boundary for readable markdown artifacts."""

    def render_shared_artifact(
        self,
        domain: str,
        artifact_family: str,
        artifact_id: str,
        snapshot_ref: SnapshotRef,
        scope_ref: ScopeRef,
    ) -> RenderedArtifact:
        """Render a shared readable artifact from canonical state."""

    def render_personal_artifact(
        self,
        domain: str,
        personal_record_id: str,
        snapshot_ref: SnapshotRef,
        scope_ref: ScopeRef,
    ) -> RenderedArtifact:
        """Render a user-scoped readable artifact from personal metadata and upstream state."""
