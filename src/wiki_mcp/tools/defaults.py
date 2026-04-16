from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wiki_mcp.services.ingestion_entrypoint import DefaultIngestionEntrypoint
from wiki_mcp.services.page_read_entrypoint import DefaultPageReadEntrypoint
from wiki_mcp.services.personal_query_entrypoint import DefaultPersonalQueryEntrypoint
from wiki_mcp.services.retrieval_read_entrypoint import DefaultRetrievalReadEntrypoint
from wiki_mcp.tools.registry import (
    ToolArgument,
    ToolDefinition,
    ToolError,
    ToolRegistry,
    ToolResultField,
)


def build_default_tool_definitions(
    *,
    ingestion_entrypoint: DefaultIngestionEntrypoint,
    page_read_entrypoint: DefaultPageReadEntrypoint,
    retrieval_read_entrypoint: DefaultRetrievalReadEntrypoint,
    personal_query_entrypoint: DefaultPersonalQueryEntrypoint,
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
                    fields=(
                        ToolArgument("source_id", "string", "Source identifier."),
                        ToolArgument("connector", "string", "Connector name."),
                        ToolArgument("domain", "string", "Domain key."),
                        ToolArgument("title", "string", "Source title."),
                        ToolArgument("body_markdown", "string", "Source body."),
                        ToolArgument("metadata", "object", "Source metadata."),
                        ToolArgument("fetched_at", "string", "Fetch timestamp."),
                        ToolArgument("content_hash", "string", "Content hash."),
                        ToolArgument("status", "string", "Source status."),
                    ),
                ),
            ),
            result_fields=(
                ToolResultField("ok", "boolean", "Whether ingestion succeeded."),
                ToolResultField(
                    "source_record_id",
                    "string",
                    "Canonical source record identifier when available.",
                    required=False,
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_source", "The normalized source payload is invalid."),
                ToolError("ingestion_failed", "The ingestion entrypoint failed."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
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
            result_fields=(
                ToolResultField("ok", "boolean", "Whether ingestion succeeded."),
                ToolResultField(
                    "source_id",
                    "string",
                    "Provider-native source identifier that was ingested.",
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_request", "The Worknet request arguments are invalid."),
                ToolError("source_fetch_failed", "Fetching the Worknet source failed."),
                ToolError("ingestion_failed", "The ingestion entrypoint failed."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
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
                    fields=(
                        ToolArgument("scope", "string", "Scope kind."),
                        ToolArgument("tenant_id", "string", "Tenant identifier.", required=False),
                        ToolArgument("user_id", "string", "User identifier.", required=False),
                    ),
                ),
            ),
            result_fields=(
                ToolResultField("ok", "boolean", "Whether the page read succeeded."),
                ToolResultField(
                    "page",
                    "object",
                    "Rendered page envelope when the page exists.",
                    required=False,
                ),
                ToolResultField(
                    "read_model_state",
                    "string",
                    "Authoritative read-model visibility state.",
                    required=False,
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("page_not_found", "The requested page does not exist."),
                ToolError("invalid_scope_ref", "The scope reference is invalid for this read."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
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
                    fields=(
                        ToolArgument("scope", "string", "Scope kind."),
                        ToolArgument("tenant_id", "string", "Tenant identifier.", required=False),
                        ToolArgument("user_id", "string", "User identifier.", required=False),
                    ),
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
            result_fields=(
                ToolResultField("ok", "boolean", "Whether the list read succeeded."),
                ToolResultField(
                    "pages",
                    "array",
                    "Rendered page summaries returned by the listing.",
                    required=False,
                ),
                ToolResultField(
                    "read_model_state",
                    "string",
                    "Authoritative read-model visibility state.",
                    required=False,
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_scope_ref", "The scope reference is invalid for this listing."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
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
            result_fields=(
                ToolResultField("ok", "boolean", "Whether the page read succeeded."),
                ToolResultField(
                    "page",
                    "object",
                    "Rendered personal page envelope when the page exists.",
                    required=False,
                ),
                ToolResultField(
                    "read_model_state",
                    "string",
                    "Authoritative read-model visibility state.",
                    required=False,
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("page_not_found", "The requested personal page does not exist."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
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
            result_fields=(
                ToolResultField("ok", "boolean", "Whether the list read succeeded."),
                ToolResultField(
                    "pages",
                    "array",
                    "Rendered personal page summaries returned by the listing.",
                    required=False,
                ),
                ToolResultField(
                    "read_model_state",
                    "string",
                    "Authoritative read-model visibility state.",
                    required=False,
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
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
            result_fields=(
                ToolResultField("ok", "boolean", "Whether the page read succeeded."),
                ToolResultField(
                    "page",
                    "object",
                    "Rendered interpretation page envelope when the page exists.",
                    required=False,
                ),
                ToolResultField(
                    "read_model_state",
                    "string",
                    "Authoritative read-model visibility state.",
                    required=False,
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("page_not_found", "The requested interpretation page does not exist."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
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
            result_fields=(
                ToolResultField("ok", "boolean", "Whether the list read succeeded."),
                ToolResultField(
                    "pages",
                    "array",
                    "Rendered shared interpretation page summaries returned by the listing.",
                    required=False,
                ),
                ToolResultField(
                    "read_model_state",
                    "string",
                    "Authoritative read-model visibility state.",
                    required=False,
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
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
                    fields=(
                        ToolArgument("scope", "string", "Scope kind."),
                        ToolArgument("tenant_id", "string", "Tenant identifier.", required=False),
                        ToolArgument("user_id", "string", "User identifier.", required=False),
                    ),
                ),
                ToolArgument(
                    "profile_context",
                    "object",
                    "Optional profile context overrides for retrieval.",
                    required=False,
                    fields=(
                        ToolArgument("target_role", "string", "Target role hint.", required=False),
                        ToolArgument("skills", "array", "Skill list.", required=False),
                    ),
                ),
            ),
            result_fields=(
                ToolResultField("ok", "boolean", "Whether retrieval succeeded."),
                ToolResultField(
                    "retrieval",
                    "object",
                    "Layered retrieval envelope for the question.",
                ),
                ToolResultField(
                    "read_model_state",
                    "string",
                    "Authoritative read-model visibility state.",
                    required=False,
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_scope_ref", "The scope reference is invalid for retrieval."),
                ToolError("retrieval_failed", "The retrieval entrypoint failed."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
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
            result_fields=(
                ToolResultField("ok", "boolean", "Whether the batch ingestion succeeded."),
                ToolResultField(
                    "command_id",
                    "string",
                    "Command identifier for tracking asynchronous batch work.",
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_fact_batch", "The fact batch request is invalid."),
                ToolError("fact_batch_not_supported_yet", "The fact batch tool is not wired yet."),
            ),
        ),
        _placeholder_tool(
            name="build_interpretation_snapshot",
            description="Future MCP interpretation projection tool contract.",
            group="interpretation",
            entrypoint="interpretation.build_snapshot",
            result_fields=(
                ToolResultField("ok", "boolean", "Whether projection submission succeeded."),
                ToolResultField(
                    "command_id",
                    "string",
                    "Command identifier for snapshot build tracking.",
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_interpretation_request", "The interpretation build request is invalid."),
                ToolError(
                    "interpretation_snapshot_not_supported_yet",
                    "The interpretation snapshot tool is not wired yet.",
                ),
            ),
        ),
        _available_tool(
            name="query_personal_knowledge",
            description="Assemble a thin personal answer on top of the current retrieval slice.",
            group="personal",
            entrypoint="personal.query_knowledge",
            arguments=(
                ToolArgument("domain", "string", "Domain key for the personal query."),
                ToolArgument("question", "string", "Natural-language question to answer."),
                ToolArgument(
                    "scope_ref",
                    "object",
                    "Resolved scope reference used for the personal answer.",
                    fields=(
                        ToolArgument("scope", "string", "Scope kind."),
                        ToolArgument("tenant_id", "string", "Tenant identifier.", required=False),
                        ToolArgument("user_id", "string", "User identifier.", required=False),
                    ),
                ),
                ToolArgument(
                    "profile_context",
                    "object",
                    "Optional profile context used during answer assembly.",
                    required=False,
                    fields=(
                        ToolArgument("user_id", "string", "User identifier.", required=False),
                        ToolArgument("tenant_id", "string", "Tenant identifier.", required=False),
                        ToolArgument("domain", "string", "Domain key.", required=False),
                        ToolArgument(
                            "profile_version",
                            "string",
                            "Profile version for the answer context.",
                            required=False,
                        ),
                        ToolArgument("goals", "array", "Profile goals.", required=False),
                        ToolArgument(
                            "preferences",
                            "object",
                            "Profile preference map.",
                            required=False,
                        ),
                        ToolArgument(
                            "attributes",
                            "object",
                            "Profile attribute map.",
                            required=False,
                        ),
                    ),
                ),
            ),
            result_fields=(
                ToolResultField("ok", "boolean", "Whether personal query execution succeeded."),
                ToolResultField(
                    "answer",
                    "object",
                    "User-scoped synthesized knowledge answer envelope.",
                ),
                ToolResultField(
                    "retrieval",
                    "object",
                    "Underlying retrieval result used to assemble the answer.",
                ),
                ToolResultField(
                    "read_model_state",
                    "string",
                    "Authoritative read-model visibility state.",
                    required=False,
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_personal_query", "The personal query is invalid."),
                ToolError("personal_query_failed", "The personal query entrypoint failed."),
                ToolError("invalid_result", "The tool returned a result that violated its contract."),
            ),
            handler=lambda arguments: _query_personal_knowledge(
                personal_query_entrypoint,
                arguments,
            ),
        ),
        _placeholder_tool(
            name="create_personal_plan",
            description="Future MCP personal generation tool contract.",
            group="personal",
            entrypoint="personal.create_plan",
            result_fields=(
                ToolResultField("ok", "boolean", "Whether plan creation submission succeeded."),
                ToolResultField(
                    "command_id",
                    "string",
                    "Command identifier for plan generation tracking.",
                ),
            ),
            errors=(
                ToolError("invalid_arguments", "Input arguments do not satisfy the tool contract."),
                ToolError("invalid_plan_request", "The personal plan request is invalid."),
                ToolError("personal_plan_not_supported_yet", "The personal plan tool is not wired yet."),
            ),
        ),
    ]


def build_default_tool_registry(
    *,
    ingestion_entrypoint: DefaultIngestionEntrypoint,
    page_read_entrypoint: DefaultPageReadEntrypoint,
    retrieval_read_entrypoint: DefaultRetrievalReadEntrypoint,
    personal_query_entrypoint: DefaultPersonalQueryEntrypoint,
) -> ToolRegistry:
    return ToolRegistry(
        build_default_tool_definitions(
            ingestion_entrypoint=ingestion_entrypoint,
            page_read_entrypoint=page_read_entrypoint,
            retrieval_read_entrypoint=retrieval_read_entrypoint,
            personal_query_entrypoint=personal_query_entrypoint,
        )
    )


def _available_tool(
    *,
    name: str,
    description: str,
    group: str,
    entrypoint: str,
    arguments: tuple[ToolArgument, ...] = (),
    result_fields: tuple[ToolResultField, ...] = (),
    errors: tuple[ToolError, ...] = (),
    handler: Any,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        group=group,
        entrypoint=entrypoint,
        arguments=arguments,
        result_fields=result_fields,
        errors=errors,
        handler=handler,
    )


def _placeholder_tool(
    *,
    name: str,
    description: str,
    group: str,
    entrypoint: str,
    arguments: tuple[ToolArgument, ...] = (),
    result_fields: tuple[ToolResultField, ...] = (),
    errors: tuple[ToolError, ...] = (),
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        group=group,
        entrypoint=entrypoint,
        arguments=arguments,
        result_fields=result_fields,
        errors=errors,
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


def _query_personal_knowledge(
    entrypoint: DefaultPersonalQueryEntrypoint,
    arguments: Mapping[str, Any],
) -> object:
    return entrypoint.query_personal_knowledge(
        domain=arguments["domain"],
        question=arguments["question"],
        scope_ref=arguments["scope_ref"],
        profile_context=arguments.get("profile_context"),
    )
