from __future__ import annotations

from pathlib import Path

from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.rendered_page import RenderedPage
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.scope_ref import ScopeRef


class FileSystemRenderingRepository:
    """Persist rendered markdown artifacts beneath a configured render root."""

    def __init__(self, render_root: str | Path) -> None:
        self.render_root = Path(render_root)

    def write_artifact(self, artifact: RenderedArtifact) -> str:
        destination = self.render_root / artifact["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact["body_markdown"], encoding="utf-8")
        return artifact["path"]

    def get_page(
        self,
        *,
        domain: str,
        layer: str,
        record_id: str,
        scope_ref: ScopeRef,
    ) -> RenderedPage | None:
        return None

    def list_pages(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        layer: str | None = None,
        limit: int = 20,
    ) -> list[RenderedPageSummary]:
        return []
