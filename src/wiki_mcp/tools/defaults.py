from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wiki_mcp.services.ingestion_entrypoint import DefaultIngestionEntrypoint
from wiki_mcp.services.page_read_entrypoint import DefaultPageReadEntrypoint
from wiki_mcp.services.retrieval_read_entrypoint import DefaultRetrievalReadEntrypoint
from wiki_mcp.tools.registry import ToolDefinition, ToolRegistry


def build_default_tool_registry(
    *,
    ingestion_entrypoint: DefaultIngestionEntrypoint,
    page_read_entrypoint: DefaultPageReadEntrypoint,
    retrieval_read_entrypoint: DefaultRetrievalReadEntrypoint,
) -> ToolRegistry:
    return ToolRegistry(
        [
            ToolDefinition(
                name="ingest_source",
                description="Ingest one normalized source through the application entrypoint.",
                handler=lambda arguments: _ingest_source(
                    ingestion_entrypoint,
                    arguments,
                ),
            ),
            ToolDefinition(
                name="ingest_worknet_source",
                description="Fetch and ingest one Worknet recruiting source.",
                handler=lambda arguments: _ingest_worknet_source(
                    ingestion_entrypoint,
                    arguments,
                ),
            ),
            ToolDefinition(
                name="get_page",
                description="Read one rendered page via the page read entrypoint.",
                handler=lambda arguments: _get_page(
                    page_read_entrypoint,
                    arguments,
                ),
            ),
            ToolDefinition(
                name="list_pages",
                description="List rendered pages via the page read entrypoint.",
                handler=lambda arguments: _list_pages(
                    page_read_entrypoint,
                    arguments,
                ),
            ),
            ToolDefinition(
                name="get_personal_page",
                description="Read one Personal rendered page.",
                handler=lambda arguments: _get_personal_page(
                    page_read_entrypoint,
                    arguments,
                ),
            ),
            ToolDefinition(
                name="list_personal_pages",
                description="List Personal rendered pages for one user scope.",
                handler=lambda arguments: _list_personal_pages(
                    page_read_entrypoint,
                    arguments,
                ),
            ),
            ToolDefinition(
                name="get_interpretation_page",
                description="Read one shared Interpretation rendered page.",
                handler=lambda arguments: _get_interpretation_page(
                    page_read_entrypoint,
                    arguments,
                ),
            ),
            ToolDefinition(
                name="list_interpretation_pages",
                description="List shared Interpretation rendered pages.",
                handler=lambda arguments: _list_interpretation_pages(
                    page_read_entrypoint,
                    arguments,
                ),
            ),
            ToolDefinition(
                name="retrieve_for_query",
                description="Resolve layered retrieval candidates through the current read authority slice.",
                handler=lambda arguments: _retrieve_for_query(
                    retrieval_read_entrypoint,
                    arguments,
                ),
            ),
            ToolDefinition(
                name="ingest_fact_batch",
                description="Future MCP fact-ingestion tool contract.",
                status="placeholder",
            ),
            ToolDefinition(
                name="build_interpretation_snapshot",
                description="Future MCP interpretation projection tool contract.",
                status="placeholder",
            ),
            ToolDefinition(
                name="query_personal_knowledge",
                description="Future MCP personal retrieval tool contract.",
                status="placeholder",
            ),
            ToolDefinition(
                name="create_personal_plan",
                description="Future MCP personal generation tool contract.",
                status="placeholder",
            ),
        ]
    )


def _ingest_source(
    entrypoint: DefaultIngestionEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.ingest_source(arguments["source"])


def _ingest_worknet_source(
    entrypoint: DefaultIngestionEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.ingest_worknet_source(
        arguments["provider"],
        arguments["source_id"],
        auth_key=arguments.get("auth_key"),
        include_raw=bool(arguments.get("include_raw", False)),
    )


def _get_page(
    entrypoint: DefaultPageReadEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.get_page(
        domain=arguments["domain"],
        layer=arguments["layer"],
        record_id=arguments["record_id"],
        scope_ref=arguments["scope_ref"],
    )


def _list_pages(
    entrypoint: DefaultPageReadEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.list_pages(
        domain=arguments["domain"],
        scope_ref=arguments["scope_ref"],
        layer=arguments.get("layer"),
        limit=int(arguments.get("limit", 20)),
    )


def _get_personal_page(
    entrypoint: DefaultPageReadEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.get_personal_page(
        domain=arguments["domain"],
        tenant_id=arguments["tenant_id"],
        user_id=arguments["user_id"],
        record_id=arguments["record_id"],
    )


def _list_personal_pages(
    entrypoint: DefaultPageReadEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.list_personal_pages(
        domain=arguments["domain"],
        tenant_id=arguments["tenant_id"],
        user_id=arguments["user_id"],
        limit=int(arguments.get("limit", 20)),
    )


def _get_interpretation_page(
    entrypoint: DefaultPageReadEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.get_interpretation_page(
        domain=arguments["domain"],
        record_id=arguments["record_id"],
    )


def _list_interpretation_pages(
    entrypoint: DefaultPageReadEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.list_interpretation_pages(
        domain=arguments["domain"],
        limit=int(arguments.get("limit", 20)),
    )


def _retrieve_for_query(
    entrypoint: DefaultRetrievalReadEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.retrieve_for_query(
        domain=arguments["domain"],
        question=arguments["question"],
        scope_ref=arguments["scope_ref"],
        profile_context=arguments.get("profile_context"),
    )
