from __future__ import annotations

from pathlib import Path

from psycopg import Connection

from wiki_mcp.server import StrataWikiServer, build_server
from wiki_mcp.tools import (
    ToolInvocationError,
    build_default_tool_definitions,
    build_default_tool_registry,
)


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
        return {"ok": True, "method": "get_page", "page": {"record_id": kwargs["record_id"]}, **kwargs}

    def list_pages(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "method": "list_pages", "pages": [], **kwargs}

    def get_personal_page(self, **kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "method": "get_personal_page",
            "page": {"record_id": kwargs["record_id"]},
            **kwargs,
        }

    def list_personal_pages(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "method": "list_personal_pages", "pages": [], **kwargs}

    def get_interpretation_page(self, **kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "method": "get_interpretation_page",
            "page": {"record_id": kwargs["record_id"]},
            **kwargs,
        }

    def list_interpretation_pages(self, **kwargs: object) -> dict[str, object]:
        return {"ok": True, "method": "list_interpretation_pages", "pages": [], **kwargs}


class StubRetrievalReadEntrypoint:
    def retrieve_for_query(self, **kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "method": "retrieve_for_query",
            "retrieval": {"question": kwargs["question"]},
            **kwargs,
        }


class BadResultRetrievalEntrypoint:
    def retrieve_for_query(self, **kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "retrieval": [],
        }


def test_default_tool_registry_exposes_wired_and_placeholder_tools() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    definitions = {definition.name: definition for definition in registry.list_tools()}

    assert definitions["ingest_source"].status == "available"
    assert definitions["ingest_source"].group == "ingestion"
    assert definitions["ingest_source"].entrypoint == "ingestion.ingest_source"
    assert definitions["ingest_source"].arguments[0].name == "source"
    assert definitions["ingest_source"].result_fields[0].name == "ok"
    assert "ingestion_failed" in {error.code for error in definitions["ingest_source"].errors}
    assert definitions["get_personal_page"].status == "available"
    assert definitions["retrieve_for_query"].status == "available"
    assert definitions["ingest_fact_batch"].status == "placeholder"
    assert definitions["ingest_fact_batch"].group == "fact"
    assert "fact_batch_not_supported_yet" in {
        error.code for error in definitions["ingest_fact_batch"].errors
    }
    assert definitions["query_personal_knowledge"].handler is None
    assert definitions["query_personal_knowledge"].entrypoint == "personal.query_knowledge"
    assert definitions["get_page"].arguments[3].fields[0].name == "scope"


def test_default_tool_definitions_are_grouped_for_contract_visibility() -> None:
    definitions = build_default_tool_definitions(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    by_name = {definition.name: definition for definition in definitions}

    assert by_name["list_pages"].group == "page_reads"
    assert by_name["retrieve_for_query"].group == "retrieval"
    assert by_name["create_personal_plan"].status == "placeholder"
    assert any(argument.name == "scope_ref" for argument in by_name["get_page"].arguments)
    assert any(field.name == "retrieval" for field in by_name["retrieve_for_query"].result_fields)


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


def test_registry_lists_tools_by_group() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    grouped = registry.list_tools_by_group()

    assert [tool.name for tool in grouped["ingestion"]] == [
        "ingest_source",
        "ingest_worknet_source",
    ]
    assert [tool.name for tool in grouped["retrieval"]] == ["retrieve_for_query"]
    assert [tool.name for tool in grouped["personal"]] == [
        "create_personal_plan",
        "query_personal_knowledge",
    ]


def test_registry_exports_public_tool_schema() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    schemas = {schema["name"]: schema for schema in registry.export_tool_schemas()}

    assert schemas["ingest_source"]["group"] == "ingestion"
    assert schemas["ingest_source"]["schema_version"] == "bootstrap.v1"
    assert schemas["ingest_source"]["arguments"][0]["name"] == "source"
    assert schemas["ingest_source"]["arguments"][0]["fields"][0]["name"] == "source_id"
    assert schemas["ingest_source"]["result"][0]["name"] == "ok"
    assert schemas["ingest_source"]["error_contract"]["fields"][0]["name"] == "code"
    assert "ingestion_failed" in {
        error["code"] for error in schemas["ingest_source"]["error_contract"]["codes"]
    }
    assert schemas["create_personal_plan"]["status"] == "placeholder"


def test_registry_validates_missing_required_argument() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    try:
        registry.call_tool(
            "get_personal_page",
            {
                "domain": "recruiting",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
            },
        )
    except ToolInvocationError as exc:
        assert exc.code == "invalid_arguments"
        assert "record_id" in exc.message
    else:
        raise AssertionError("Expected missing required argument to fail.")


def test_registry_validates_argument_types() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    try:
        registry.call_tool(
            "list_personal_pages",
            {
                "domain": "recruiting",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "limit": "20",
            },
        )
    except ToolInvocationError as exc:
        assert exc.code == "invalid_arguments"
        assert "integer" in exc.message
    else:
        raise AssertionError("Expected invalid argument type to fail.")


def test_registry_validates_nested_argument_types() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    try:
        registry.call_tool(
            "retrieve_for_query",
            {
                "domain": "recruiting",
                "question": "backend transition plan",
                "scope_ref": {
                    "scope": "user",
                    "tenant_id": 7,
                },
            },
        )
    except ToolInvocationError as exc:
        assert exc.code == "invalid_arguments"
        assert "tenant_id" in exc.message
    else:
        raise AssertionError("Expected nested argument validation to fail.")


def test_registry_validates_result_contract() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=BadResultRetrievalEntrypoint(),
    )

    try:
        registry.call_tool(
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
    except ToolInvocationError as exc:
        assert exc.code == "invalid_result"
        assert "retrieval" in exc.message
    else:
        raise AssertionError("Expected invalid tool result to fail.")


def test_registry_returns_structured_error_envelope() -> None:
    registry = build_default_tool_registry(
        ingestion_entrypoint=StubIngestionEntrypoint(),
        page_read_entrypoint=StubPageReadEntrypoint(),
        retrieval_read_entrypoint=StubRetrievalReadEntrypoint(),
    )

    result = registry.call_tool_with_envelope(
        "get_personal_page",
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
        },
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


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
        assert "page_reads" in server.list_tools_by_group()
        assert any(schema["name"] == "retrieve_for_query" for schema in server.export_tool_schemas())
        assert server.call_tool_with_envelope(
            "get_personal_page",
            {
                "domain": "recruiting",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
            },
        )["ok"] is False
    finally:
        server.close()
