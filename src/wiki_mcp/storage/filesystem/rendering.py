from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wiki_mcp.schemas.rendered_artifact import RenderedArtifact
from wiki_mcp.schemas.rendered_page import RenderedPage
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.scope_ref import ScopeRef
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

    def read_markdown(self, path: str) -> str:
        stored_path = self.root_dir / path
        return stored_path.read_text(encoding="utf-8")


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

    def get_page(
        self,
        *,
        domain: str,
        layer: str,
        record_id: str,
        scope_ref: ScopeRef,
    ) -> RenderedPage | None:
        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
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
                FROM graph.rendered_page
                WHERE domain = %s
                  AND layer = %s
                  AND record_id = %s
                  AND {scope_sql}
                """,
                [domain, layer, record_id, *scope_params],
            )
            row = cursor.fetchone()

        if row is None:
            return None

        summary = self._row_to_rendered_page_summary(row)
        return {
            **summary,
            "body_markdown": self.filesystem_repository.read_markdown(summary["path"]),
        }

    def list_pages(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        layer: str | None = None,
        limit: int = 20,
    ) -> list[RenderedPageSummary]:
        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        filters = ["domain = %s", scope_sql]
        params: list[object] = [domain, *scope_params]

        if layer is not None:
            filters.append("layer = %s")
            params.append(layer)

        params.append(limit)

        where_sql = " AND ".join(filters)
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
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
                FROM graph.rendered_page
                WHERE {where_sql}
                ORDER BY updated_at DESC, path ASC
                LIMIT %s
                """,
                params,
            )
            return [self._row_to_rendered_page_summary(row) for row in cursor.fetchall()]

    def _scope_filter_sql(self, scope_ref: ScopeRef) -> tuple[str, list[object]]:
        scope = scope_ref["scope"]
        clauses = ["scope = %s"]
        params: list[object] = [scope]

        if scope == "tenant":
            clauses.append("tenant_id = %s")
            params.append(scope_ref.get("tenant_id"))
        elif scope == "user":
            clauses.append("tenant_id = %s")
            clauses.append("user_id = %s")
            params.append(scope_ref.get("tenant_id"))
            params.append(scope_ref.get("user_id"))

        return " AND ".join(clauses), params

    def _row_to_rendered_page_summary(self, row: Any) -> RenderedPageSummary:
        data = dict(row)
        metadata = self._load_json(data.get("metadata_json"))
        return {
            "domain": data["domain"],
            "layer": data["layer"],
            "record_id": data["record_id"],
            "path": data["path"],
            "title": str(metadata.get("title") or data["record_id"]),
            "scope_ref": {
                "scope": data["scope"],
                **({"tenant_id": data["tenant_id"]} if data.get("tenant_id") else {}),
                **({"user_id": data["user_id"]} if data.get("user_id") else {}),
            },
            "snapshot_ref": {
                "fact_snapshot_id": data["fact_snapshot_id"],
                **(
                    {"interpretation_snapshot_id": data["interpretation_snapshot_id"]}
                    if data.get("interpretation_snapshot_id")
                    else {}
                ),
                **({"profile_version": data["profile_version"]} if data.get("profile_version") else {}),
            },
            "metadata": metadata,
        }

    def _load_json(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        return json.loads(value)
