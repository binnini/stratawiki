from __future__ import annotations

import json
import re
from uuid import uuid4
from pathlib import Path

from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.rendered_page import RenderedPage
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.scope_ref import ScopeRef


class FileSystemRenderingRepository:
    """Persist rendered markdown artifacts beneath a configured render root."""

    rendered_page_marker = "stratawiki:rendered_page"

    def __init__(self, render_root: str | Path) -> None:
        self.render_root = Path(render_root)

    def write_artifact(self, artifact: RenderedArtifact) -> str:
        destination = self.render_root / artifact["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact["body_markdown"], encoding="utf-8")
        return artifact["path"]

    def replace_artifact_atomically(self, artifact: RenderedArtifact) -> dict[str, object]:
        destination = self.render_root / artifact["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)

        replacement_id = uuid4().hex
        stage_path = self.render_root / ".staging" / f"{replacement_id}.md"
        stage_path.parent.mkdir(parents=True, exist_ok=True)
        stage_path.write_text(artifact["body_markdown"], encoding="utf-8")

        backup_path: Path | None = None
        try:
            if destination.exists():
                backup_path = self.render_root / ".replacements" / f"{replacement_id}.bak"
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                destination.replace(backup_path)
            stage_path.replace(destination)
        except Exception:
            if stage_path.exists():
                stage_path.unlink()
            if backup_path is not None and backup_path.exists() and not destination.exists():
                backup_path.replace(destination)
            raise

        return {
            "path": artifact["path"],
            "destination_path": str(destination),
            **({"backup_path": str(backup_path)} if backup_path is not None else {}),
        }

    def commit_artifact_replacement(self, receipt: dict[str, object]) -> None:
        backup_path_text = receipt.get("backup_path")
        if isinstance(backup_path_text, str):
            backup_path = Path(backup_path_text)
            if backup_path.exists():
                backup_path.unlink()

    def rollback_artifact_replacement(self, receipt: dict[str, object]) -> None:
        destination_path = Path(str(receipt["destination_path"]))
        backup_path_text = receipt.get("backup_path")
        backup_path = Path(backup_path_text) if isinstance(backup_path_text, str) else None

        if backup_path is not None and backup_path.exists():
            if destination_path.exists():
                destination_path.unlink()
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.replace(destination_path)
            return

        if destination_path.exists():
            destination_path.unlink()

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
        for path in self._iter_markdown_paths(scope_ref):
            page = self._load_rendered_page(path)
            if page is None:
                continue
            if page["domain"] != domain or page["layer"] != layer or page["record_id"] != record_id:
                continue
            return page
        return None

    def list_pages(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        layer: str | None = None,
        limit: int = 20,
    ) -> list[RenderedPageSummary]:
        pages: list[tuple[float, RenderedPageSummary]] = []
        for path in self._iter_markdown_paths(scope_ref):
            page = self._load_rendered_page(path)
            if page is None or page["domain"] != domain:
                continue
            if layer is not None and page["layer"] != layer:
                continue
            pages.append(
                (
                    path.stat().st_mtime,
                    {
                        "domain": page["domain"],
                        "layer": page["layer"],
                        "record_id": page["record_id"],
                        "path": page["path"],
                        "title": page["title"],
                        "scope_ref": page["scope_ref"],
                        "snapshot_ref": page["snapshot_ref"],
                        "metadata": page["metadata"],
                    },
                )
            )
        pages.sort(key=lambda item: (-item[0], item[1]["path"]))
        return [summary for _, summary in pages[:limit]]

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

    def _iter_markdown_paths(self, scope_ref: ScopeRef) -> list[Path]:
        root = self._scope_root(scope_ref)
        if not root.exists():
            return []
        return [path for path in root.rglob("*.md") if path.is_file()]

    def _scope_root(self, scope_ref: ScopeRef) -> Path:
        scope = scope_ref["scope"]
        if scope == "user":
            return self.render_root / "wiki" / "users" / str(scope_ref["user_id"])
        if scope == "tenant":
            return self.render_root / "wiki" / "tenants" / str(scope_ref["tenant_id"])
        return self.render_root / "wiki" / "shared"

    def _load_rendered_page(self, path: Path) -> RenderedPage | None:
        raw = path.read_text(encoding="utf-8")
        match = re.search(
            rf"<!--\s*{self.rendered_page_marker}\s*(\{{.*?\}})\s*-->",
            raw,
            re.DOTALL,
        )
        if match is None:
            return None

        try:
            metadata = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
        if not isinstance(metadata, dict):
            return None

        try:
            return {
                "domain": str(metadata["domain"]),
                "layer": str(metadata["layer"]),
                "record_id": str(metadata["record_id"]),
                "path": str(metadata["path"]),
                "title": str(metadata["title"]),
                "scope_ref": dict(metadata["scope_ref"]),
                "snapshot_ref": dict(metadata["snapshot_ref"]),
                "metadata": dict(metadata.get("metadata") or {}),
                "body_markdown": raw[match.end():].lstrip("\n"),
            }
        except (KeyError, TypeError, ValueError):
            return None
