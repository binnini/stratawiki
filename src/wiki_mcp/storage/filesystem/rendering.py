from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.storage.postgres.base import managed_cursor


class FilesystemRenderingRepository:
    """Persist readable rendered artifacts to the local filesystem."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def write_artifact(self, artifact: RenderedArtifact) -> str:
        path = self.root_dir / artifact["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(artifact["body_markdown"], encoding="utf-8")
        return str(path)


class FilesystemAndPostgresRenderingRepository:
    """Persist rendered artifacts to the filesystem and graph.rendered_page."""

    def __init__(self, root_dir: str | Path, connection: Any) -> None:
        self.filesystem_repository = FilesystemRenderingRepository(root_dir)
        self.connection = connection

    def write_artifact(self, artifact: RenderedArtifact) -> str:
        stored_path = self.filesystem_repository.write_artifact(artifact)
        scope_ref = artifact["scope_ref"]
        snapshot_ref = artifact["snapshot_ref"]

        metadata_json = json.dumps({"title": artifact["title"]}, ensure_ascii=False)
        params = (
            artifact["path"],
            snapshot_ref["fact_snapshot_id"],
            snapshot_ref.get("interpretation_snapshot_id"),
            snapshot_ref.get("profile_version"),
            metadata_json,
            artifact["domain"],
            artifact["layer"],
            artifact["record_id"],
            scope_ref["scope"],
            scope_ref.get("tenant_id"),
            scope_ref.get("user_id"),
        )

        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                UPDATE graph.rendered_page
                SET
                    path = %s,
                    fact_snapshot_id = %s,
                    interpretation_snapshot_id = %s,
                    profile_version = %s,
                    metadata_json = %s::jsonb,
                    updated_at = NOW()
                WHERE domain = %s
                  AND layer = %s
                  AND record_id = %s
                  AND scope = %s
                  AND COALESCE(tenant_id, '') = COALESCE(%s, '')
                  AND COALESCE(user_id, '') = COALESCE(%s, '')
                """,
                params,
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    INSERT INTO graph.rendered_page (
                        domain,
                        layer,
                        record_id,
                        path,
                        scope,
                        tenant_id,
                        user_id,
                        fact_snapshot_id,
                        interpretation_snapshot_id,
                        profile_version,
                        metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        artifact["domain"],
                        artifact["layer"],
                        artifact["record_id"],
                        artifact["path"],
                        scope_ref["scope"],
                        scope_ref.get("tenant_id"),
                        scope_ref.get("user_id"),
                        snapshot_ref["fact_snapshot_id"],
                        snapshot_ref.get("interpretation_snapshot_id"),
                        snapshot_ref.get("profile_version"),
                        metadata_json,
                    ),
                )

        return stored_path
