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

    def read_body(
        self,
        *,
        path: str,
        scope_ref: ScopeRef,
    ) -> str | None:
        normalized_path = path.lstrip("/")
        if not self._path_allowed_for_scope(normalized_path, scope_ref):
            return None

        resolved_root = self.render_root.resolve()
        resolved_path = (self.render_root / normalized_path).resolve()
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            return None
        if not resolved_path.exists() or not resolved_path.is_file():
            return None
        return resolved_path.read_text(encoding="utf-8")

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

    def _path_allowed_for_scope(
        self,
        path: str,
        scope_ref: ScopeRef,
    ) -> bool:
        scope = scope_ref["scope"]
        if scope == "user":
            user_id = scope_ref.get("user_id")
            return isinstance(user_id, str) and path.startswith(f"wiki/users/{user_id}/")
        if scope == "tenant":
            tenant_id = scope_ref.get("tenant_id")
            return isinstance(tenant_id, str) and path.startswith(f"wiki/tenants/{tenant_id}/")
        return path.startswith("wiki/shared/")
