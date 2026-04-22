from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wiki_mcp.services.personal_document_bodies import PersonalDocumentBodyStore


@dataclass(frozen=True, slots=True)
class PersonalMarkdownMigrationRow:
    id: str
    path: str
    updated_at: str
    provenance_json: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PersonalMarkdownMigrationUpdate:
    subspace: str
    asset_refs_json: list[str]
    version: int
    created_at: str
    content_hash: str
    provenance_json: dict[str, Any]


_LEGACY_BODY_MARKERS = (
    "stratawiki:personal_document",
    "stratawiki:personal_query_answer",
)


def migrate_personal_markdown_canonical(
    *,
    database_url: str,
    render_root: str | Path,
    rewrite_files: bool = False,
    prune_legacy_provenance: bool = False,
) -> dict[str, int]:
    import psycopg
    from psycopg.rows import dict_row

    render_root_path = Path(render_root)
    body_store = PersonalDocumentBodyStore(rendering_repository=object())
    migrated = 0
    rewritten = 0

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, path, updated_at::text AS updated_at, provenance_json
                FROM personal.record
                ORDER BY updated_at ASC, id ASC
                """
            )
            rows = [
                PersonalMarkdownMigrationRow(
                    id=str(row["id"]),
                    path=str(row["path"]),
                    updated_at=str(row["updated_at"]),
                    provenance_json=_load_json(row.get("provenance_json")),
                )
                for row in cursor.fetchall()
            ]

        for row in rows:
            file_path = render_root_path / row.path
            raw_body = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            legacy_metadata, canonical_markdown = _parse_legacy_personal_body(raw_body)
            canonical_body = body_store.render_body(canonical_markdown)
            legacy_storage = _legacy_storage(row.provenance_json)
            update = PersonalMarkdownMigrationUpdate(
                subspace=_infer_subspace(
                    path=row.path,
                    provenance=row.provenance_json,
                    legacy_metadata=legacy_metadata,
                ),
                asset_refs_json=_normalize_string_list(
                    legacy_metadata.get("asset_refs") or legacy_storage.get("asset_refs")
                ),
                version=_positive_int(
                    legacy_metadata.get("version") or legacy_storage.get("version"),
                    default=1,
                ),
                created_at=str(
                    legacy_metadata.get("created_at")
                    or legacy_storage.get("created_at")
                    or row.updated_at
                ),
                content_hash=body_store.content_hash(canonical_markdown),
                provenance_json=_pruned_provenance(
                    row.provenance_json,
                    prune_legacy_provenance=prune_legacy_provenance,
                ),
            )

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE personal.record
                    SET subspace = %s,
                        asset_refs_json = %s::jsonb,
                        version = %s,
                        created_at = %s::timestamptz,
                        content_hash = %s,
                        provenance_json = %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        update.subspace,
                        json.dumps(update.asset_refs_json),
                        update.version,
                        update.created_at,
                        update.content_hash,
                        json.dumps(update.provenance_json),
                        row.id,
                    ),
                )
            migrated += 1

            if rewrite_files and raw_body != canonical_body and file_path.exists():
                file_path.write_text(canonical_body, encoding="utf-8")
                rewritten += 1

        connection.commit()

    return {"migrated_records": migrated, "rewritten_files": rewritten}


def _load_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        return {}
    return json.loads(value)


def _legacy_storage(provenance_json: dict[str, Any]) -> dict[str, Any]:
    storage = provenance_json.get("_personal_document")
    if isinstance(storage, dict):
        return dict(storage)
    return {}


def _infer_subspace(
    *,
    path: str,
    provenance: dict[str, Any],
    legacy_metadata: dict[str, Any] | None = None,
) -> str:
    storage = _legacy_storage(provenance)
    metadata = legacy_metadata or {}
    metadata_subspace = metadata.get("subspace")
    if isinstance(metadata_subspace, str) and metadata_subspace in {"raw", "wiki"}:
        return metadata_subspace
    raw_subspace = storage.get("subspace")
    if isinstance(raw_subspace, str) and raw_subspace in {"raw", "wiki"}:
        return raw_subspace
    if "/documents/wiki/" in path or "/answers/" in path:
        return "wiki"
    return "raw"


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _positive_int(value: Any, *, default: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    return default


def _pruned_provenance(
    provenance_json: dict[str, Any],
    *,
    prune_legacy_provenance: bool,
) -> dict[str, Any]:
    if not prune_legacy_provenance:
        return dict(provenance_json)
    next_value = dict(provenance_json)
    next_value.pop("_personal_document", None)
    return next_value


def _parse_legacy_personal_body(raw_body: str | None) -> tuple[dict[str, Any], str]:
    if not isinstance(raw_body, str) or not raw_body.strip():
        return {}, ""
    for marker in _LEGACY_BODY_MARKERS:
        match = re.search(
            rf"<!--\s*{re.escape(marker)}\s*(\{{.*?\}})\s*-->",
            raw_body,
            re.DOTALL,
        )
        if match is None:
            continue
        try:
            metadata = json.loads(match.group(1))
        except json.JSONDecodeError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return metadata, raw_body[match.end():].lstrip("\n").rstrip("\n")
    return {}, raw_body.rstrip("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill Personal markdown-canonical metadata and optionally rewrite legacy files."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://stratawiki:stratawiki@localhost:5432/stratawiki"),
    )
    parser.add_argument("--render-root", default="data")
    parser.add_argument("--rewrite-files", action="store_true")
    parser.add_argument("--prune-legacy-provenance", action="store_true")
    args = parser.parse_args(argv)

    result = migrate_personal_markdown_canonical(
        database_url=str(args.database_url),
        render_root=str(args.render_root),
        rewrite_files=bool(args.rewrite_files),
        prune_legacy_provenance=bool(args.prune_legacy_provenance),
    )
    print(json.dumps({"status": "ok", **result}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
