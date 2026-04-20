from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from wiki_mcp.bootstrap import connect_postgres
from wiki_mcp.demo import load_demo_seed
from wiki_mcp.storage.postgres.base import managed_cursor

if TYPE_CHECKING:
    from wiki_mcp.server import StrataWikiServer


BootstrapConnectionFactory = Callable[[str | None], Any]

DEFAULT_POSTGRES_BOOTSTRAP_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "postgres" / "bootstrap.sql"
)


def apply_postgres_bootstrap(
    *,
    database_url: str | None = None,
    bootstrap_sql_path: str | Path | None = None,
    connect: BootstrapConnectionFactory = connect_postgres,
) -> dict[str, object]:
    sql_path = Path(bootstrap_sql_path or DEFAULT_POSTGRES_BOOTSTRAP_PATH)
    try:
        bootstrap_sql = sql_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to read bootstrap SQL from {sql_path}: {exc}") from exc

    connection = connect(database_url)
    try:
        with managed_cursor(connection) as cursor:
            cursor.execute(bootstrap_sql)
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            is_closed = getattr(connection, "closed", False)
            if not is_closed:
                close()

    return {
        "status": "ok",
        "bootstrap_sql_path": str(sql_path),
    }


def run_mvp_seed_flow(
    server: StrataWikiServer,
    *,
    seed_path: str | Path,
) -> dict[str, object]:
    seed = load_demo_seed(seed_path)
    _persist_seed_profiles(server, seed.profiles)

    query = seed.demo_query
    partition = seed.demo_partition
    ingest = server.call_tool(
        "ingest_fact_batch",
        {"domain": query["domain"], "source_records": seed.source_records},
    )
    build = server.call_tool(
        "build_interpretation_snapshot",
        {
            "domain": query["domain"],
            "partition": partition,
            "fact_ids": ingest["affected_fact_ids"],
            "fact_snapshot": ingest["fact_snapshot"],
            "model_profile": query["model_profile"],
            "publish": True,
        },
    )
    personal_query = server.call_tool("query_personal_knowledge", query)
    snapshot = server.call_tool(
        "get_snapshot_status",
        {"domain": query["domain"], "partition": {"family": partition["family"]}},
    )
    return {
        "status": "ok",
        "seed_path": str(Path(seed_path)),
        "seeded_profiles": len(seed.profiles),
        "steps": {
            "ingest_fact_batch": ingest,
            "build_interpretation_snapshot": build,
            "query_personal_knowledge": personal_query,
            "get_snapshot_status": snapshot,
        },
    }


def _persist_seed_profiles(server: StrataWikiServer, profiles: list[dict[str, Any]]) -> None:
    repository = server.bootstrap.profile_context_repository
    if repository is None or not hasattr(repository, "save_profile_context"):
        raise ValueError("Profile context repository does not support local seed writes.")

    for profile in profiles:
        repository.save_profile_context(profile)
