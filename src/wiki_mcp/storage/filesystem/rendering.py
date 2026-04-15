from __future__ import annotations

from pathlib import Path

from wiki_mcp.schemas.rendered_artifact import RenderedArtifact


class FilesystemRenderingRepository:
    """Persist readable rendered artifacts to the local filesystem."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def write_artifact(self, artifact: RenderedArtifact) -> str:
        path = self.root_dir / artifact["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(artifact["body_markdown"], encoding="utf-8")
        return str(path)
