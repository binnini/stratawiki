from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wiki_mcp.services.ingestion_entrypoint import DefaultIngestionEntrypoint
from wiki_mcp.services.page_read_entrypoint import DefaultPageReadEntrypoint
from wiki_mcp.services.retrieval_read_entrypoint import DefaultRetrievalReadEntrypoint
from wiki_mcp.tools.registry import ToolArgument, ToolDefinition, ToolRegistry


def build_default_tool_definitions(
    *,
    ingestion_entrypoint: DefaultIngestionEntrypoint,
    page_read_entrypoint: DefaultPageReadEntrypoint,
    retrieval_read_entrypoint: DefaultRetrievalReadEntrypoint,
) -> list[ToolDefinition]:
    return [
        _available_tool(
            name="ingest_source",
            description="Ingest one normalized source through the application entrypoint.",
            group="ingestion",
            entrypoint="ingestion.ingest_source",
            arguments=(
                ToolArgument(
                    name="source",
                    value_type="object",
                    description="Normalized source payload to persist and project.",
                ),
            ),
            handler=lambda arguments: _ingest_source(
                ingestion_entrypoint,
                arguments,
            ),
        ),
        _available_tool(
            name="ingest_worknet_source",
            description="Fetch and ingest one Worknet recruiting source.",
            group="ingestion",
            entrypoint="ingestion.ingest_worknet_source",
            arguments=(
                ToolArgument(
                    name="provider",
                    value_type="string",
                    description="Worknet provider name or provider enum value.",
                ),
                ToolArgument(
                    name="source_id",
                    value_type="string",
                    description="Provider-native source identifier.",
                ),
                ToolArgument(
                    name="auth_key",
                    value_type="string",
                    description="Optional Worknet API key override.",
                    required=False,
                ),
                ToolArgument(
                    name="include_raw",
                    value_type="boolean",
                    description="Whether to include the raw payload in the result.",
                    required=False,
                ),
            ),
            handler=lambda arguments: _ingest_worknet_source(
                ingestion_entrypoint,
                arguments,
            ),
        ),
        _available_tool(
            name="get_page",
            description="Read one rendered page via the page read entrypoint.",
            group="page_reads",
            entrypoint="page_reads.get_page",
            arguments=(
                ToolArgument("domain", "string", "Domain key for the rendered page."),
                ToolArgument("layer", "string", "Knowledge layer to read from."),
                ToolArgument("record_id", "string", "Canonical record identifier."),
                ToolArgument(
                    "scope_ref",
                    "object",
                    "Resolved scope reference for the requested page.",
                ),
            ),
            handler=lambda arguments: _get_page(
                page_read_entrypoint,
                arguments,
            ),
        ),
        _available_tool(
            name="list_pages",
            description="List rendered pages via the page read entrypoint.",
            group="page_reads",
            entrypoint="page_reads.list_pages",
            arguments=(
                ToolArgument("domain", "string", "Domain key for the rendered pages."),
                ToolArgument(
                    "scope_ref",
                    "object",
                    "Resolved scope reference used to constrain listing.",
                ),
                ToolArgument(
                    "layer",
                    "string",
                    "Optional layer filter for the rendered pages.",
                    required=False,
                ),
                ToolArgument(
                    "limit",
                    "integer",
                    "Maximum number of rendered pages to return.",
                    required=False,
                ),
            ),
            handler=lambda arguments: _list_pages(
                page_read_entrypoint,
                arguments,
            ),
        ),
        _available_tool(
            name="get_personal_page",
            description="Read one Personal rendered page.",
            group="page_reads",
            entrypoint="page_reads.get_personal_page",
            arguments=(
                ToolArgument("domain", "string", "Domain key for the rendered page."),
                ToolArgument("tenant_id", "string", "Tenant scope for the page."),
                ToolArgument("user_id", "string", "User scope for the page."),
                ToolArgument("record_id", "string", "Personal record identifier."),
            ),
            handler=lambda arguments: _get_personal_page(
                page_read_entrypoint,
                arguments,
            ),
        ),
        _available_tool(
            name="list_personal_pages",
            description="List Personal rendered pages for one user scope.",
            group="page_reads",
            entrypoint="page_reads.list_personal_pages",
            arguments=(
                ToolArgument("domain", "string", "Domain key for the rendered pages."),
                ToolArgument("tenant_id", "string", "Tenant scope for the listing."),
                ToolArgument("user_id", "string", "User scope for the listing."),
                ToolArgument(
                    "limit",
                    "integer",
                    "Maximum number of personal pages to return.",
                    required=False,
                ),
            ),
            handler=lambda arguments: _list_personal_pages(
                page_read_entrypoint,
                arguments,
            ),
        ),
        _available_tool(
            name="get_interpretation_page",
            description="Read one shared Interpretation rendered page.",
            group="page_reads",
            entrypoint="page_reads.get_interpretation_page",
            arguments=(
                ToolArgument("domain", "string", "Domain key for the rendered page."),
                ToolArgument(
                    "record_id",
                    "string",
                    "Shared interpretation record identifier.",
                ),
            ),
            handler=lambda arguments: _get_interpretation_page(
                page_read_entrypoint,
                arguments,
            ),
        ),
        _available_tool(
            name="list_interpretation_pages",
            description="List shared Interpretation rendered pages.",
            group="page_reads",
            entrypoint="page_reads.list_interpretation_pages",
            arguments=(
                ToolArgument("domain", "string", "Domain key for the rendered pages."),
                ToolArgument(
                    "limit",
                    "integer",
                    "Maximum number of shared interpretation pages to return.",
                    required=False,
                ),
            ),
            handler=lambda arguments: _list_interpretation_pages(
                page_read_entrypoint,
                arguments,
            ),
        ),
        _available_tool(
            name="retrieve_for_query",
            description="Resolve layered retrieval candidates through the current read authority slice.",
            group="retrieval",
            entrypoint="retrieval_reads.retrieve_for_query",
            arguments=(
                ToolArgument("domain", "string", "Domain key for retrieval."),
                ToolArgument("question", "string", "Natural-language retrieval prompt."),
                ToolArgument(
                    "scope_ref",
                    "object",
                    "Resolved scope reference used for layered retrieval.",
                ),
                ToolArgument(
                    "profile_context",
                    "object",
                    "Optional profile context overrides for retrieval.",
                    required=False,
                ),
            ),
            handler=lambda arguments: _retrieve_for_query(
                retrieval_read_entrypoint,
                arguments,
            ),
        ),
        _placeholder_tool(
            name="ingest_fact_batch",
            description="Future MCP fact-ingestion tool contract.",
            group="fact",
            entrypoint="fact.ingest_batch",
        ),
        _placeholder_tool(
            name="build_interpretation_snapshot",
            description="Future MCP interpretation projection tool contract.",
            group="interpretation",
            entrypoint="interpretation.build_snapshot",
        ),
        _placeholder_tool(
            name="query_personal_knowledge",
            description="Future MCP personal retrieval tool contract.",
            group="personal",
            entrypoint="personal.query_knowledge",
        ),
        _placeholder_tool(
            name="create_personal_plan",
            description="Future MCP personal generation tool contract.",
            group="personal",
            entrypoint="personal.create_plan",
        ),
    ]


def build_default_tool_registry(
    *,
    ingestion_entrypoint: DefaultIngestionEntrypoint,
    page_read_entrypoint: DefaultPageReadEntrypoint,
    retrieval_read_entrypoint: DefaultRetrievalReadEntrypoint,
) -> ToolRegistry:
    return ToolRegistry(
        build_default_tool_definitions(
            ingestion_entrypoint=ingestion_entrypoint,
            page_read_entrypoint=page_read_entrypoint,
            retrieval_read_entrypoint=retrieval_read_entrypoint,
        )
    )


def _available_tool(
    *,
    name: str,
    description: str,
    group: str,
    entrypoint: str,
    arguments: tuple[ToolArgument, ...] = (),
    handler: Any,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        group=group,
        entrypoint=entrypoint,
        arguments=arguments,
        handler=handler,
    )


def _placeholder_tool(
    *,
    name: str,
    description: str,
    group: str,
    entrypoint: str,
    arguments: tuple[ToolArgument, ...] = (),
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        group=group,
        entrypoint=entrypoint,
        arguments=arguments,
        status="placeholder",
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
