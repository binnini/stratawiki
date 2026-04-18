from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from wiki_mcp.bootstrap import BootstrapContext, bootstrap_application
from wiki_mcp.domains.recruiting import RecruitingSourceIngestionPlugin
from wiki_mcp.services.interpretation_families import InterpretationProposalContext
from wiki_mcp.tools import ToolDefinition


def _tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="ingest_fact_batch",
            group="fact",
            status="mvp",
            description="Ingest normalized source records into the Fact layer.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "source_records"],
                "properties": {
                    "domain": {"type": "string"},
                    "source_records": {"type": "array"},
                },
            },
        ),
        ToolDefinition(
            name="validate_domain_proposal_batch",
            group="fact",
            status="mvp",
            description="Validate one DomainProposalBatch against the active Domain Pack.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["batch"],
                "properties": {
                    "batch": {"type": "object"},
                },
            },
        ),
        ToolDefinition(
            name="ingest_domain_proposal_batch",
            group="fact",
            status="mvp",
            description="Ingest one DomainProposalBatch through the canonical proposal gateway.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["batch"],
                "properties": {
                    "batch": {"type": "object"},
                },
            },
        ),
        ToolDefinition(
            name="get_fact_record",
            group="fact",
            status="mvp",
            description="Return one canonical Fact record.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "fact_id"],
                "properties": {
                    "domain": {"type": "string"},
                    "fact_id": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="build_interpretation_snapshot",
            group="interpretation",
            status="mvp",
            description="Build and publish one interpretation snapshot on the happy path.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "partition", "fact_ids"],
                "properties": {
                    "domain": {"type": "string"},
                    "partition": {"type": "object"},
                    "fact_ids": {"type": "array"},
                    "model_profile": {"type": "string"},
                    "publish": {"type": "boolean"},
                },
            },
        ),
        ToolDefinition(
            name="get_interpretation_record",
            group="interpretation",
            status="mvp",
            description="Return one interpretation record.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "interpretation_id"],
                "properties": {
                    "domain": {"type": "string"},
                    "interpretation_id": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="query_personal_knowledge",
            group="personal",
            status="mvp",
            description="Run the default Personal -> Interpretation -> Fact query flow.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": [
                    "domain",
                    "tenant_id",
                    "user_id",
                    "question",
                    "profile_version",
                    "model_profile",
                ],
                "properties": {
                    "domain": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "question": {"type": "string"},
                    "profile_version": {"type": "string"},
                    "model_profile": {"type": "string"},
                    "save": {"type": "boolean"},
                },
            },
        ),
        ToolDefinition(
            name="get_snapshot_status",
            group="snapshot",
            status="mvp",
            description="Return the current published snapshot pointers.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain"],
                "properties": {
                    "domain": {"type": "string"},
                    "partition": {"type": "object"},
                },
            },
        ),
    ]


@dataclass(slots=True)
class StrataWikiServer:
    bootstrap: BootstrapContext

    def list_tools(self) -> list[ToolDefinition]:
        return _tool_definitions()

    def list_tools_by_group(self) -> dict[str, list[ToolDefinition]]:
        groups: dict[str, list[ToolDefinition]] = {}
        for tool in self.list_tools():
            groups.setdefault(tool.group, []).append(tool)
        return groups

    def export_tool_schemas(self) -> list[dict[str, object]]:
        return [tool.export_schema() for tool in self.list_tools()]

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> object:
        args = arguments or {}
        if name == "ingest_fact_batch":
            return self._ingest_fact_batch(args)
        if name == "validate_domain_proposal_batch":
            return self._validate_domain_proposal_batch(args)
        if name == "ingest_domain_proposal_batch":
            return self._ingest_domain_proposal_batch(args)
        if name == "get_fact_record":
            return self._get_fact_record(args)
        if name == "build_interpretation_snapshot":
            return self._build_interpretation_snapshot(args)
        if name == "get_interpretation_record":
            return self._get_interpretation_record(args)
        if name == "query_personal_knowledge":
            return self._query_personal_knowledge(args)
        if name == "get_snapshot_status":
            return self._get_snapshot_status(args)
        raise KeyError(f"Unknown tool: {name}")

    def call_tool_with_envelope(self, name: str, arguments: dict[str, object] | None = None) -> dict[str, object]:
        try:
            result = self.call_tool(name, arguments)
        except Exception as exc:
            return {"ok": False, "error": exc.__class__.__name__, "message": str(exc)}
        return {"ok": True, "result": result}

    def close(self) -> None:
        self.bootstrap.close()

    def _ingest_fact_batch(self, arguments: dict[str, object]) -> dict[str, object]:
        source_records = arguments.get("source_records")
        if not isinstance(source_records, list) or not source_records:
            raise ValueError("ingest_fact_batch requires a non-empty source_records list.")
        domain = self._required_string(arguments, "domain")
        plugin = RecruitingSourceIngestionPlugin()
        aggregate: dict[str, Any] = {
            "status": "ok",
            "fact_snapshot": "",
            "facts_created": 0,
            "facts_updated": 0,
            "facts_superseded": 0,
            "affected_fact_ids": [],
        }
        for raw_source in source_records:
            if not isinstance(raw_source, dict):
                raise ValueError("Each source_records item must be an object.")
            if raw_source.get("domain") != domain:
                raise ValueError("All source_records items must match the requested domain.")
            result = self.bootstrap.core_ingestion_service.ingest_source(raw_source, plugin)
            aggregate["fact_snapshot"] = result["fact_snapshot_id"]
            aggregate["facts_created"] += result["facts_created"]
            aggregate["facts_updated"] += result["facts_updated"]
            aggregate["affected_fact_ids"].extend(result["affected_fact_ids"])
        return aggregate

    def _get_fact_record(self, arguments: dict[str, object]) -> dict[str, object]:
        self._required_string(arguments, "domain")
        fact_id = self._required_string(arguments, "fact_id")
        records = self.bootstrap.fact_repository.get_by_ids([fact_id], self._scope_ref(arguments, default_scope="shared"))
        if not records:
            raise KeyError(f"Unknown fact record: {fact_id}")
        return {"status": "ok", "record": records[0]}

    def _validate_domain_proposal_batch(self, arguments: dict[str, object]) -> dict[str, object]:
        batch = arguments.get("batch")
        if not isinstance(batch, dict):
            raise ValueError("validate_domain_proposal_batch requires a batch object.")
        service = self.bootstrap.domain_proposal_ingestion_service
        if service is None:
            raise ValueError("Domain proposal ingestion service is not configured.")
        return service.validate_batch(batch)

    def _ingest_domain_proposal_batch(self, arguments: dict[str, object]) -> dict[str, object]:
        batch = arguments.get("batch")
        if not isinstance(batch, dict):
            raise ValueError("ingest_domain_proposal_batch requires a batch object.")
        service = self.bootstrap.domain_proposal_ingestion_service
        if service is None:
            raise ValueError("Domain proposal ingestion service is not configured.")
        return service.ingest_batch(batch)

    def _build_interpretation_snapshot(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        partition = arguments.get("partition")
        if not isinstance(partition, dict):
            raise ValueError("build_interpretation_snapshot requires a partition object.")
        family = self._normalize_family(self._required_string(partition, "family"))
        subject_id = self._required_string(partition, "segment", fallback_key="subject_id")
        fact_ids = arguments.get("fact_ids")
        if not isinstance(fact_ids, list) or not fact_ids:
            raise ValueError("build_interpretation_snapshot requires a non-empty fact_ids list.")
        facts = self.bootstrap.fact_repository.get_by_ids([str(item) for item in fact_ids], {"scope": "shared"})
        if not facts:
            raise ValueError("No facts were found for the supplied fact_ids.")
        fact_snapshot = self._required_string(
            arguments,
            "fact_snapshot",
            fallback_key="fact_snapshot_id",
            default=facts[0].get("fact_snapshot_id"),
        )
        model_profile = str(arguments.get("model_profile") or "balanced_default")
        publish = bool(arguments.get("publish", True))
        builder = self.bootstrap.interpretation_family_registry.get(family)
        if builder is None and family != "market_trend":
            raise ValueError(f"No interpretation builder is registered for family {family!r}.")
        if builder is not None and hasattr(builder, "model_profile"):
            setattr(builder, "model_profile", model_profile)
        context = InterpretationProposalContext(
            domain=domain,
            family=family,
            subject_type="market_segment",
            subject_id=subject_id,
            scope_ref={"scope": "shared"},
            fact_snapshot_id=fact_snapshot,
            schema_version="interpretation.v2",
            facts=facts,
            provenance={
                "generated_by": {"kind": "llm", "prompt_version": "interp.market_trend.v1"},
                "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
        )
        proposals = self.bootstrap.interpretation_proposal_service.create_proposals(context)
        if not proposals:
            raise ValueError("No interpretation proposals were generated for the supplied partition.")
        interpretation_snapshot = ""
        records_superseded = 0
        if publish:
            for proposal in proposals:
                publication = self.bootstrap.interpretation_publication_service.publish_proposal(
                    proposal_id=proposal["id"],
                    scope_ref={"scope": "shared"},
                )
                if not publication["ok"]:
                    raise ValueError(f"Failed to publish interpretation proposal {proposal['id']}.")
                interpretation_snapshot = publication["interpretation_snapshot_id"]
                records_superseded += len(publication["superseded_ids"])
        return {
            "status": "ok",
            "interpretation_snapshot": interpretation_snapshot,
            "records_created": len(proposals),
            "records_updated": 0,
            "records_superseded": records_superseded,
        }

    def _get_interpretation_record(self, arguments: dict[str, object]) -> dict[str, object]:
        self._required_string(arguments, "domain")
        interpretation_id = self._required_string(arguments, "interpretation_id")
        record = self.bootstrap.interpretation_query_service.get_interpretation_record(
            record_id=interpretation_id,
            scope_ref=self._scope_ref(arguments, default_scope="shared"),
        )
        if record is None:
            raise KeyError(f"Unknown interpretation record: {interpretation_id}")
        return {"status": "ok", "record": record}

    def _query_personal_knowledge(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        tenant_id = self._required_string(arguments, "tenant_id")
        user_id = self._required_string(arguments, "user_id")
        question = self._required_string(arguments, "question")
        requested_profile_version = self._required_string(arguments, "profile_version")
        model_profile = self._required_string(arguments, "model_profile")
        profile_context = self.bootstrap.profile_context_repository.get_profile_context(domain, tenant_id, user_id)
        if profile_context["profile_version"] != requested_profile_version:
            raise ValueError("Requested profile_version does not match the current stored profile context.")
        answer = self.bootstrap.personal_query_service.query_personal_knowledge(
            domain=domain,
            question=question,
            scope_ref={"scope": "user", "tenant_id": tenant_id, "user_id": user_id},
            profile_context=profile_context,
            model_profile=model_profile,
            save=bool(arguments.get("save", False)),
        )
        return {
            "status": "ok",
            "answer_markdown": answer["answer_markdown"],
            "personal_records_used": answer["personal_records_used"],
            "interpretation_records_used": answer["interpretation_records_used"],
            "fact_records_used": answer["fact_records_used"],
            "provenance": answer["provenance"],
        }

    def _get_snapshot_status(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        partition = arguments.get("partition")
        layer = "interpretation" if isinstance(partition, dict) else None
        status = self.bootstrap.snapshot_repository.get_snapshot_status(domain=domain, layer=layer)
        if status is None:
            raise KeyError(f"No published snapshot status exists for domain {domain!r}.")
        return {
            "status": "ok",
            "fact_snapshot": status["fact_snapshot_id"],
            **({"interpretation_snapshot": status["interpretation_snapshot_id"]} if "interpretation_snapshot_id" in status else {}),
            **({"published_at": status["published_at"]} if "published_at" in status else {}),
        }

    def _required_string(
        self,
        arguments: dict[str, object],
        key: str,
        *,
        fallback_key: str | None = None,
        default: object | None = None,
    ) -> str:
        value = arguments.get(key)
        if value is None and fallback_key is not None:
            value = arguments.get(fallback_key)
        if value is None:
            value = default
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing required string argument: {key}")
        return value.strip()

    def _scope_ref(self, arguments: dict[str, object], *, default_scope: str) -> dict[str, str]:
        scope = str(arguments.get("scope") or default_scope)
        scope_ref: dict[str, str] = {"scope": scope}
        tenant_id = arguments.get("tenant_id")
        user_id = arguments.get("user_id")
        if isinstance(tenant_id, str) and tenant_id:
            scope_ref["tenant_id"] = tenant_id
        if isinstance(user_id, str) and user_id:
            scope_ref["user_id"] = user_id
        return scope_ref

    def _normalize_family(self, family: str) -> str:
        normalized = family.strip().lower()
        if normalized == "market_trends":
            return "market_trend"
        return normalized


def build_server(
    *,
    connection: Any | None = None,
    database_url: str | None = None,
    render_root: str = "data",
    demo_mode: bool = False,
    seed_path: str | None = None,
    domain_pack_paths: list[str] | None = None,
    active_domain_pack_versions: dict[str, str] | None = None,
) -> StrataWikiServer:
    bootstrap = bootstrap_application(
        connection=connection,
        database_url=database_url,
        render_root=render_root,
        demo_mode=demo_mode,
        seed_path=seed_path,
        domain_pack_paths=domain_pack_paths,
        active_domain_pack_versions=active_domain_pack_versions,
    )
    return StrataWikiServer(bootstrap=bootstrap)


def main() -> None:
    server = build_server()
    try:
        print("StrataWiki MVP tool runtime ready.")
        print(f"Registered tools: {', '.join(tool.name for tool in server.list_tools())}")
    finally:
        server.close()
