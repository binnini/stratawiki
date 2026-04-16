from __future__ import annotations

from pathlib import Path

from psycopg import Connection

from wiki_mcp.server import StrataWikiServer, build_server
from wiki_mcp.tools import build_default_tool_registry


class StubIngestionEntrypoint:
    def __init__(self) -> None:
        self.sources: list[dict[str, object]] = []

    def ingest_source(self, source: dict[str, object]) -> dict[str, object]:
        self.sources.append(source)
        return {"ok": True, "source": source}

    def ingest_worknet_source(
        self,
        provider: object,
        source_id: str,
        *,
        auth_key: str | None = None,
        include_raw: bool = False,
    ) -> dict[str, object]:
        return {
            "ok": True,
            "provider": provider,
            "source_id": source_id,
            "auth_key": auth_key,
            "include_raw": include_raw,
        }


class StubPageReadEntrypoint:
    def get_page(self, **kwargs: object) -> dict[str, object]:
        return {"method": "get_page", **kwargs}

    def list_pages(self, **kwargs: object) -> dict[str, object]:
        return {"method": "list_pages", **kwargs}

    def get_personal_page(self, **kwargs: object) -> dict[str, object]:
        return {"method": "get_personal_page", **kwargs}

    def list_personal_pages(self, **kwargs: object) -> dict[str, object]:
        return {"method": "list_personal_pages", **kwargs}

    def get_interpretation_page(self, **kwargs: object) -> dict[str, object]:
        return {"method": "get_interpretation_page", **kwargs}

    def list_interpretation_pages(self, **kwargs: object) -> dict[str, object]:
        return {"method": "list_interpretation_pages", **kwargs}


class StubRetrievalReadEntrypoint:
    def retrieve_for_query(self, **kwargs: object) -> dict[str, object]:
        return {"method": "retrieve_for_query", **kwargs}


def test_default_tool_registry_exposes_wired_and_placeholder_tools() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    definitions = {definition.name: definition for definition in registry.list_tools()}

    assert definitions["ingest_source"].status == "available"
    assert definitions["get_personal_page"].status == "available"
    assert definitions["retrieve_for_query"].status == "available"
    assert definitions["ingest_fact_batch"].status == "placeholder"
    assert definitions["query_personal_knowledge"].handler is None


def test_default_tool_registry_dispatches_to_entrypoints() -> None:
    ingestion_entrypoint = StubIngestionEntrypoint()
    registry = build_default_tool_registry(
        ingestion_entrypoint=ingestion_entrypoint,
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    ingest_result = registry.call_tool(
        "ingest_source",
        {
            "source": {
                "source_id": "EMP-1",
                "connector": "worknet",
                "domain": "recruiting",
                "title": "Backend Engineer",
                "body_markdown": "test",
                "metadata": {},
                "fetched_at": "2026-04-16T00:00:00Z",
                "content_hash": "hash-1",
                "status": "active",
            }
        },
    )
    page_result = registry.call_tool(
        "get_personal_page",
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "record_id": "personal:plan-1",
        },
    )
    retrieval_result = registry.call_tool(
        "retrieve_for_query",
        {
            "domain": "recruiting",
            "question": "backend transition plan",
            "scope_ref": {
                "scope": "user",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
            },
        },
    )

    assert ingest_result["ok"] is True
    assert ingestion_entrypoint.sources[0]["source_id"] == "EMP-1"
    assert page_result["method"] == "get_personal_page"
    assert retrieval_result["method"] == "retrieve_for_query"


def test_placeholder_tool_cannot_be_called() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    try:
        registry.call_tool("ingest_fact_batch", {})
    except NotImplementedError as exc:
        assert "placeholder" in str(exc)
    else:
        raise AssertionError("Expected placeholder tool call to fail.")


def test_build_server_wires_postgres_entrypoints_and_tools(
    postgres_connection: Connection[dict],
    tmp_path: Path,
) -> None:
    with postgres_connection.cursor() as cursor:
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
                "recruiting",
                "personal",
                "personal:plan-1",
                "wiki/personal/tenant-1/user-1/plan-1.md",
                "user",
                "tenant-1",
                "user-1",
                "fact_snap:new",
                "interp_snap:new",
                "profile-v2",
                '{"title": "Backend transition plan"}',
            ),
        )
    postgres_connection.commit()

    stored_path = tmp_path / "wiki/personal/tenant-1/user-1/plan-1.md"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_text("# Backend transition plan\n", encoding="utf-8")

    server = build_server(connection=postgres_connection, render_root=tmp_path)
    try:
        result = server.call_tool(
            "get_personal_page",
            {
                "domain": "recruiting",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "record_id": "personal:plan-1",
            },
        )
        retrieval_result = server.call_tool(
            "retrieve_for_query",
            {
                "domain": "recruiting",
                "question": "backend transition plan",
                "scope_ref": {
                    "scope": "user",
                    "tenant_id": "tenant-1",
                    "user_id": "user-1",
                },
            },
        )

        assert isinstance(server, StrataWikiServer)
        assert result["ok"] is True
        assert result["page"]["record_id"] == "personal:plan-1"
        assert retrieval_result["ok"] is True
        assert retrieval_result["retrieval"]["personal_ids"] == ["personal:plan-1"]
        assert "ingest_source" in {tool.name for tool in server.list_tools()}
    finally:
        server.close()
