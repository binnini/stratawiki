from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Mapping

from wiki_mcp.bootstrap import connect_postgres
from wiki_mcp.demo import DEFAULT_DEMO_SEED_PATH
from wiki_mcp.runtime_setup import DEFAULT_POSTGRES_BOOTSTRAP_PATH
from wiki_mcp.services.domain_pack_artifacts import resolve_domain_pack_paths
from wiki_mcp.storage.postgres.base import managed_cursor


DEFAULT_RENDER_ROOT_ENV = "STRATAWIKI_RENDER_ROOT"
DEFAULT_BOOTSTRAP_SQL_ENV = "STRATAWIKI_POSTGRES_BOOTSTRAP_SQL"
DEFAULT_SEED_PATH_ENV = "STRATAWIKI_SEED_PATH"

REQUIRED_BOOTSTRAP_RELATIONS = (
    "fact.record_envelopes",
    "fact.relation_envelopes",
    "interp.record",
    "personal.record",
    "personal.profile_context",
    "ops.snapshot_pointer",
    "ops.snapshot_publication",
    "ops.outbox_event",
    "graph.dependency_edge",
    "graph.rendered_page",
)


def resolve_render_root(render_root: str | Path | None = None) -> Path:
    if render_root is not None:
        return Path(render_root)

    raw = os.environ.get(DEFAULT_RENDER_ROOT_ENV, "").strip()
    if raw:
        return Path(raw)
    return Path("data")


def resolve_seed_path(seed_path: str | Path | None = None) -> Path:
    if seed_path is not None:
        return Path(seed_path)

    raw = os.environ.get(DEFAULT_SEED_PATH_ENV, "").strip()
    if raw:
        return Path(raw)
    return Path(DEFAULT_DEMO_SEED_PATH)


def resolve_bootstrap_sql_path(bootstrap_sql_path: str | Path | None = None) -> Path:
    if bootstrap_sql_path is not None:
        return Path(bootstrap_sql_path)

    raw = os.environ.get(DEFAULT_BOOTSTRAP_SQL_ENV, "").strip()
    if raw:
        return Path(raw)
    return Path(DEFAULT_POSTGRES_BOOTSTRAP_PATH)


def validate_runtime_prerequisites(
    *,
    database_url: str | None = None,
    render_root: str | Path | None = None,
    domain_pack_paths: Sequence[str | Path] | None = None,
    require_bootstrap_tables: bool = True,
    connect: Any = connect_postgres,
) -> dict[str, object]:
    resolved_render_root = resolve_render_root(render_root).expanduser()
    resolved_render_root.mkdir(parents=True, exist_ok=True)
    if not resolved_render_root.is_dir():
        raise ValueError(
            f"Render root {resolved_render_root} is not a directory."
        )
    if not os.access(resolved_render_root, os.W_OK):
        raise ValueError(
            f"Render root {resolved_render_root} is not writable."
        )

    resolved_bootstrap_sql = resolve_bootstrap_sql_path().expanduser().resolve()
    if not resolved_bootstrap_sql.is_file():
        raise ValueError(
            "Configured bootstrap SQL does not exist: "
            f"{resolved_bootstrap_sql}"
        )

    resolved_domain_pack_paths = (
        [Path(path).expanduser().resolve() for path in domain_pack_paths]
        if domain_pack_paths is not None
        else resolve_domain_pack_paths(None)
    )
    missing_domain_packs = [
        str(path) for path in resolved_domain_pack_paths if not path.is_file()
    ]
    if missing_domain_packs:
        raise ValueError(
            "Configured domain pack artifacts do not exist: "
            + ", ".join(sorted(missing_domain_packs))
        )

    connection = connect(database_url)
    try:
        missing_relations: list[str] = []
        if require_bootstrap_tables:
            missing_relations = _missing_bootstrap_relations(connection)
            if missing_relations:
                raise ValueError(
                    "Postgres runtime is missing bootstrap tables: "
                    + ", ".join(missing_relations)
                    + ". Run `stratawiki init-db` before starting the server or worker."
                )
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            is_closed = getattr(connection, "closed", False)
            if not is_closed:
                close()

    return {
        "status": "ok",
        "render_root": str(resolved_render_root.resolve()),
        "bootstrap_sql_path": str(resolved_bootstrap_sql),
        "domain_pack_paths": [str(path) for path in resolved_domain_pack_paths],
        "bootstrap_tables_checked": require_bootstrap_tables,
        "checked_relations": list(REQUIRED_BOOTSTRAP_RELATIONS)
        if require_bootstrap_tables
        else [],
    }


def _missing_bootstrap_relations(connection: Any) -> list[str]:
    missing: list[str] = []
    with managed_cursor(connection) as cursor:
        for relation in REQUIRED_BOOTSTRAP_RELATIONS:
            cursor.execute(
                "SELECT to_regclass(%s) AS relation_name",
                (relation,),
            )
            row = cursor.fetchone()
            relation_name = _read_relation_name(row)
            if not relation_name:
                missing.append(relation)
    return missing


def _read_relation_name(row: object) -> str | None:
    if row is None:
        return None
    if isinstance(row, Mapping):
        value = row.get("relation_name")
        return str(value) if value is not None else None
    if isinstance(row, (list, tuple)) and row:
        value = row[0]
        return str(value) if value is not None else None
    return None
