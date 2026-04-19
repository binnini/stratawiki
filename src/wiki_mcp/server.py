from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from wiki_mcp.bootstrap import BootstrapContext, bootstrap_application
from wiki_mcp.domains.recruiting import RecruitingSourceIngestionPlugin
from wiki_mcp.schemas import (
    INTERPRETATION_LIFECYCLE_STATUSES,
    INTERPRETATION_STATUS_PROPOSED,
    INTERPRETATION_STATUS_PUBLISHED,
    INTERPRETATION_STATUS_REJECTED,
    INTERPRETATION_STATUS_STALE,
    INTERPRETATION_STATUS_SUPERSEDED,
    INTERPRETATION_STATUS_VALIDATED,
)
from wiki_mcp.services.interpretation_families import InterpretationProposalContext
from wiki_mcp.tools import ToolDefinition


def _tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="ingest_fact_batch",
            group="fact",
            status="mvp",
            description=(
                "Legacy transition path for normalized source records. "
                "External integration clients should prefer DomainProposalBatch "
                "via validate_domain_proposal_batch and ingest_domain_proposal_batch."
            ),
            entrypoint="server.call_tool",
            contract_status="legacy_transition",
            recommended_for_external_clients=False,
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
            description=(
                "Preferred external dry-run write contract. "
                "Validate one DomainProposalBatch against the active Domain Pack."
            ),
            entrypoint="server.call_tool",
            contract_status="preferred_external_write",
            recommended_for_external_clients=True,
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
            description=(
                "Preferred external write contract. "
                "Ingest one DomainProposalBatch through the canonical proposal gateway."
            ),
            entrypoint="server.call_tool",
            contract_status="preferred_external_write",
            recommended_for_external_clients=True,
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
            description=(
                "Build and publish one interpretation snapshot on the happy path, "
                "or queue the build for worker execution."
            ),
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
                    "execution_mode": {"type": "string"},
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
            name="list_interpretation_proposals",
            group="interpretation",
            status="mvp",
            description="List non-public interpretation proposals for operator review.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain"],
                "properties": {
                    "domain": {"type": "string"},
                    "partition": {"type": "object"},
                    "status": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        ),
        ToolDefinition(
            name="validate_interpretation_proposal",
            group="interpretation",
            status="mvp",
            description="Validate one proposed interpretation candidate for later publication.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "proposal_id"],
                "properties": {
                    "domain": {"type": "string"},
                    "proposal_id": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="publish_interpretation_partition",
            group="interpretation",
            status="mvp",
            description="Publish validated interpretation proposals for one family partition.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "partition"],
                "properties": {
                    "domain": {"type": "string"},
                    "partition": {"type": "object"},
                    "source_state": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="get_interpretation_proposal_status",
            group="interpretation",
            status="mvp",
            description="Return lifecycle and review status for one interpretation proposal.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "proposal_id"],
                "properties": {
                    "domain": {"type": "string"},
                    "proposal_id": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="upsert_profile_context",
            group="personal",
            status="mvp",
            description="Create or update one profile context required for Personal queries.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": [
                    "domain",
                    "tenant_id",
                    "user_id",
                    "profile_version",
                    "goals",
                    "preferences",
                    "attributes",
                ],
                "properties": {
                    "domain": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "profile_version": {"type": "string"},
                    "goals": {"type": "array"},
                    "preferences": {"type": "object"},
                    "attributes": {"type": "object"},
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
                    "fact_snapshot": {"type": "string"},
                    "interpretation_snapshot": {"type": "string"},
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
        ToolDefinition(
            name="get_cache_status",
            group="snapshot",
            status="mvp",
            description="Inspect whether one saved Personal output is fresh, stale, invalid, or missing.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "tenant_id", "user_id", "record_id"],
                "properties": {
                    "domain": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "record_id": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="get_graph_neighbors",
            group="graph",
            status="mvp",
            description="Return direct Personal/Interpretation/Fact neighbors for one node.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "node_id"],
                "properties": {
                    "domain": {"type": "string"},
                    "node_id": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        ),
        ToolDefinition(
            name="get_dependency_impact",
            group="graph",
            status="mvp",
            description="Return downstream records affected by one Fact or Interpretation change.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "record_id", "record_type"],
                "properties": {
                    "domain": {"type": "string"},
                    "record_id": {"type": "string"},
                    "record_type": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="get_job_status",
            group="operator",
            status="mvp",
            description="Inspect one queued or processed background job.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["job_id"],
                "properties": {
                    "job_id": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="explain_result",
            group="operator",
            status="mvp",
            description="Explain which snapshots and anchors produced one result, and why it changed.",
            entrypoint="server.call_tool",
            input_schema={
                "type": "object",
                "required": ["domain", "result_id"],
                "properties": {
                    "domain": {"type": "string"},
                    "result_id": {"type": "string"},
                    "layer": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "user_id": {"type": "string"},
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
        if name == "list_interpretation_proposals":
            return self._list_interpretation_proposals(args)
        if name == "validate_interpretation_proposal":
            return self._validate_interpretation_proposal(args)
        if name == "publish_interpretation_partition":
            return self._publish_interpretation_partition(args)
        if name == "get_interpretation_proposal_status":
            return self._get_interpretation_proposal_status(args)
        if name == "upsert_profile_context":
            return self._upsert_profile_context(args)
        if name == "query_personal_knowledge":
            return self._query_personal_knowledge(args)
        if name == "get_snapshot_status":
            return self._get_snapshot_status(args)
        if name == "get_cache_status":
            return self._get_cache_status(args)
        if name == "get_graph_neighbors":
            return self._get_graph_neighbors(args)
        if name == "get_dependency_impact":
            return self._get_dependency_impact(args)
        if name == "get_job_status":
            return self._get_job_status(args)
        if name == "explain_result":
            return self._explain_result(args)
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
        aggregate["warnings"] = [
            "ingest_fact_batch remains available for transition and internal source-driven flows. "
            "External integration clients should prefer validate_domain_proposal_batch and "
            "ingest_domain_proposal_batch."
        ]
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
        execution_mode = str(arguments.get("execution_mode") or "inline").strip().lower()
        if execution_mode not in {"inline", "background"}:
            raise ValueError("build_interpretation_snapshot execution_mode must be either 'inline' or 'background'.")

        request = self._parse_interpretation_build_request(arguments)
        if execution_mode == "background":
            outbox_repository = self.bootstrap.outbox_repository
            if outbox_repository is None:
                raise ValueError("Interpretation background execution requires an outbox repository.")
            event_ids = outbox_repository.append_events(
                [self._build_interpretation_snapshot_requested_event(request)]
            )
            event_id = event_ids[0]
            return {
                "status": "queued",
                "execution_mode": "background",
                "job_id": event_id,
                "event_id": event_id,
                "event_type": "interpretation_snapshot_build_requested",
            }
        return self._run_interpretation_snapshot_build(request)

    def _parse_interpretation_build_request(self, arguments: dict[str, object]) -> dict[str, object]:
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
        return {
            "domain": domain,
            "partition": {
                "family": family,
                "segment": subject_id,
            },
            "fact_ids": [fact["id"] for fact in facts],
            "fact_snapshot": fact_snapshot,
            "model_profile": model_profile,
            "publish": publish,
        }

    def _run_interpretation_snapshot_build(self, request: dict[str, object]) -> dict[str, object]:
        domain = str(request["domain"])
        partition = request["partition"]
        if not isinstance(partition, dict):
            raise ValueError("Interpretation build request is missing a partition object.")
        family = self._normalize_family(str(partition["family"]))
        subject_id = str(partition["segment"])
        fact_ids = request["fact_ids"]
        if not isinstance(fact_ids, list) or not fact_ids:
            raise ValueError("Interpretation build request requires fact_ids.")
        facts = self.bootstrap.fact_repository.get_by_ids([str(item) for item in fact_ids], {"scope": "shared"})
        if not facts:
            raise ValueError("No facts were found for the supplied fact_ids.")
        fact_snapshot = str(request["fact_snapshot"])
        model_profile = str(request.get("model_profile") or "balanced_default")
        publish = bool(request.get("publish", True))
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
        stale_personal_ids: list[str] = []
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
                stale_personal_ids.extend(
                    self._mark_personal_records_stale_for_interpretation_refresh(
                        domain=domain,
                        publication=publication,
                    )
                )
        return {
            "status": "ok",
            "interpretation_snapshot": interpretation_snapshot,
            "records_created": len(proposals),
            "records_updated": 0,
            "records_superseded": records_superseded,
            **(
                {"stale_personal_ids": self._dedupe_strings(stale_personal_ids)}
                if stale_personal_ids
                else {}
            ),
        }

    def _build_interpretation_snapshot_requested_event(
        self,
        request: dict[str, object],
    ) -> dict[str, object]:
        partition = request["partition"]
        if not isinstance(partition, dict):
            raise ValueError("Interpretation build request is missing partition metadata.")
        segment = str(partition["segment"])
        return {
            "event_type": "interpretation_snapshot_build_requested",
            "aggregate_layer": "interpretation",
            "aggregate_id": f"{request['domain']}:{partition['family']}:{segment}",
            "payload": {
                **request,
                "scope": "shared",
            },
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

    def _list_interpretation_proposals(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        partition = self._optional_interpretation_partition(arguments)
        status_filter = arguments.get("status")
        statuses = (
            [self._interpretation_status(status_filter, field="status")]
            if status_filter is not None
            else [
                INTERPRETATION_STATUS_PROPOSED,
                INTERPRETATION_STATUS_VALIDATED,
                INTERPRETATION_STATUS_REJECTED,
                INTERPRETATION_STATUS_SUPERSEDED,
            ]
        )
        records = self.bootstrap.interpretation_repository.list_records(
            domain=domain,
            scope_ref={"scope": "shared"},
            family=partition["family"] if partition is not None else None,
            subject_id=partition["subject_id"] if partition is not None else None,
            statuses=statuses,
            limit=self._optional_limit(arguments, default=50),
        )
        return {
            "status": "ok",
            "items": [self._proposal_summary(record) for record in records],
        }

    def _validate_interpretation_proposal(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        proposal_id = self._required_string(arguments, "proposal_id")
        self._require_interpretation_record(domain=domain, proposal_id=proposal_id)
        result = self.bootstrap.interpretation_proposal_service.validate_proposal(
            proposal_id=proposal_id,
            scope_ref={"scope": "shared"},
        )
        return {
            "status": "ok",
            "proposal_id": proposal_id,
            "ok": result["ok"],
            "validation_state": result["status"],
            "review_state": self._proposal_review_state(str(result["status"])),
            "errors": result["errors"],
        }

    def _publish_interpretation_partition(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        partition = self._required_interpretation_partition(arguments)
        source_state = self._interpretation_status(
            arguments.get("source_state", INTERPRETATION_STATUS_VALIDATED),
            field="source_state",
        )
        candidates = self.bootstrap.interpretation_repository.list_records(
            domain=domain,
            scope_ref={"scope": "shared"},
            family=partition["family"],
            subject_id=partition["subject_id"],
            statuses=[source_state],
            limit=50,
        )
        if not candidates:
            raise KeyError(
                "No interpretation proposals matched "
                f"domain={domain!r}, family={partition['family']!r}, "
                f"subject_id={partition['subject_id']!r}, source_state={source_state!r}."
            )

        published_proposal_ids: list[str] = []
        superseded_ids: list[str] = []
        stale_personal_ids: list[str] = []
        failures: list[dict[str, object]] = []
        interpretation_snapshot = ""
        for candidate in candidates:
            publication = self.bootstrap.interpretation_publication_service.publish_proposal(
                proposal_id=str(candidate["id"]),
                scope_ref={"scope": "shared"},
            )
            if not publication["ok"]:
                failures.append(
                    {
                        "proposal_id": candidate["id"],
                        "status": publication["status"],
                        "errors": publication["errors"],
                    }
                )
                continue
            published_proposal_ids.append(str(candidate["id"]))
            superseded_ids.extend(str(record_id) for record_id in publication["superseded_ids"])
            interpretation_snapshot = str(publication["interpretation_snapshot_id"])
            stale_personal_ids.extend(
                self._mark_personal_records_stale_for_interpretation_refresh(
                    domain=domain,
                    publication=publication,
                )
            )

        return {
            "status": "ok" if not failures else "partial",
            "source_state": source_state,
            "published_records": len(published_proposal_ids),
            "published_proposal_ids": published_proposal_ids,
            **({"interpretation_snapshot": interpretation_snapshot} if interpretation_snapshot else {}),
            "superseded_ids": superseded_ids,
            **(
                {"stale_personal_ids": self._dedupe_strings(stale_personal_ids)}
                if stale_personal_ids
                else {}
            ),
            **({"failures": failures} if failures else {}),
        }

    def _get_interpretation_proposal_status(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        proposal_id = self._required_string(arguments, "proposal_id")
        record = self._require_interpretation_record(domain=domain, proposal_id=proposal_id)
        lifecycle_state = str(record["status"])
        return {
            "status": "ok",
            "proposal_id": proposal_id,
            "lifecycle_state": lifecycle_state,
            "review_state": self._proposal_review_state(lifecycle_state),
            "family": record.get("family"),
            "subject_id": record.get("subject_id"),
            "title": record.get("title"),
            "summary": record.get("summary"),
            **(
                {"interpretation_snapshot": record["interpretation_snapshot_id"]}
                if record.get("interpretation_snapshot_id")
                else {}
            ),
        }

    def _upsert_profile_context(self, arguments: dict[str, object]) -> dict[str, object]:
        repository = self.bootstrap.profile_context_repository
        if repository is None:
            raise ValueError("Profile context repository is not configured.")
        profile_context = self._parse_profile_context(arguments)
        repository.save_profile_context(profile_context)
        return {
            "status": "ok",
            "profile_context": profile_context,
        }

    def _query_personal_knowledge(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        tenant_id = self._required_string(arguments, "tenant_id")
        user_id = self._required_string(arguments, "user_id")
        question = self._required_string(arguments, "question")
        requested_profile_version = self._required_string(arguments, "profile_version")
        model_profile = self._required_string(arguments, "model_profile")
        snapshot_ref_override = self._personal_query_snapshot_override(arguments, domain=domain)
        profile_context = self.bootstrap.profile_context_repository.get_profile_context(domain, tenant_id, user_id)
        if profile_context["profile_version"] != requested_profile_version:
            raise ValueError("Requested profile_version does not match the current stored profile context.")
        answer = self.bootstrap.personal_query_service.query_personal_knowledge(
            domain=domain,
            question=question,
            scope_ref={"scope": "user", "tenant_id": tenant_id, "user_id": user_id},
            profile_context=profile_context,
            model_profile=model_profile,
            snapshot_ref_override=snapshot_ref_override,
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

    def _personal_query_snapshot_override(
        self,
        arguments: dict[str, object],
        *,
        domain: str,
    ) -> dict[str, str] | None:
        fact_snapshot = self._optional_string(arguments, "fact_snapshot") or self._optional_string(
            arguments,
            "fact_snapshot_id",
        )
        interpretation_snapshot = self._optional_string(
            arguments,
            "interpretation_snapshot",
        ) or self._optional_string(arguments, "interpretation_snapshot_id")

        if fact_snapshot is None or interpretation_snapshot is None:
            status = self.bootstrap.snapshot_repository.get_snapshot_status(domain=domain, layer=None)
            layers = self._snapshot_layers(status)
            fact_status = layers.get("fact")
            interpretation_status = layers.get("interpretation")
            if fact_snapshot is None and fact_status is not None:
                current_fact_snapshot = fact_status.get("fact_snapshot_id")
                if isinstance(current_fact_snapshot, str) and current_fact_snapshot:
                    fact_snapshot = current_fact_snapshot
            if interpretation_snapshot is None and interpretation_status is not None:
                current_interpretation_snapshot = interpretation_status.get("interpretation_snapshot_id")
                if isinstance(current_interpretation_snapshot, str) and current_interpretation_snapshot:
                    interpretation_snapshot = current_interpretation_snapshot

        snapshot_ref_override: dict[str, str] = {}
        if fact_snapshot is not None:
            snapshot_ref_override["fact_snapshot_id"] = fact_snapshot
        if interpretation_snapshot is not None:
            snapshot_ref_override["interpretation_snapshot_id"] = interpretation_snapshot
        return snapshot_ref_override or None

    def _get_snapshot_status(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        partition = arguments.get("partition")
        layer = "interpretation" if isinstance(partition, dict) else None
        status = self.bootstrap.snapshot_repository.get_snapshot_status(domain=domain, layer=layer)
        if status is None:
            raise KeyError(f"No published snapshot status exists for domain {domain!r}.")
        if layer is None:
            layers = self._snapshot_layers(status)
            if not layers:
                raise KeyError(f"No published snapshot status exists for domain {domain!r}.")
            fact_status = layers.get("fact")
            interpretation_status = layers.get("interpretation")
            return {
                "status": "ok",
                **(
                    {"fact_snapshot": fact_status["fact_snapshot_id"]}
                    if fact_status is not None
                    else {}
                ),
                **(
                    {"interpretation_snapshot": interpretation_status["interpretation_snapshot_id"]}
                    if interpretation_status is not None
                    and "interpretation_snapshot_id" in interpretation_status
                    else {}
                ),
                "layers": layers,
            }
        return {
            "status": "ok",
            "fact_snapshot": status["fact_snapshot_id"],
            **({"interpretation_snapshot": status["interpretation_snapshot_id"]} if "interpretation_snapshot_id" in status else {}),
            **({"published_at": status["published_at"]} if "published_at" in status else {}),
        }

    def _get_cache_status(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        tenant_id = self._required_string(arguments, "tenant_id")
        user_id = self._required_string(arguments, "user_id")
        record_id = self._required_string(arguments, "record_id")
        scope_ref = {"scope": "user", "tenant_id": tenant_id, "user_id": user_id}
        snapshot_status = self.bootstrap.snapshot_repository.get_snapshot_status(
            domain=domain,
            layer=None,
        )
        if snapshot_status is None:
            raise KeyError(f"No published snapshot status exists for domain {domain!r}.")

        current_snapshots = self._current_cache_snapshots(
            domain=domain,
            tenant_id=tenant_id,
            user_id=user_id,
            snapshot_status=snapshot_status,
        )
        records = self.bootstrap.personal_repository.get_by_ids([record_id], scope_ref)
        if not records:
            return {
                "status": "ok",
                "record_id": record_id,
                "cache_state": "missing",
                "reason": "record_not_found",
                "current_snapshots": current_snapshots,
            }

        record = records[0]
        record_snapshots = self._personal_record_snapshots(record)
        cache_state, reason = self._personal_cache_state(
            current_snapshots=current_snapshots,
            record_snapshots=record_snapshots,
        )

        return {
            "status": "ok",
            "record_id": record_id,
            "cache_state": cache_state,
            "reason": reason,
            "current_snapshots": current_snapshots,
            "record_snapshots": record_snapshots,
        }

    def _get_graph_neighbors(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        node_id = self._required_string(arguments, "node_id")
        limit = self._optional_limit(arguments, default=50)
        layer = self._graph_node_layer(arguments, node_id=node_id)
        if layer == "personal":
            tenant_id = self._required_string(arguments, "tenant_id")
            user_id = self._required_string(arguments, "user_id")
            neighbors = self._personal_graph_neighbors(
                domain=domain,
                node_id=node_id,
                tenant_id=tenant_id,
                user_id=user_id,
                limit=limit,
            )
        elif layer == "interpretation":
            neighbors = self._interpretation_graph_neighbors(
                domain=domain,
                node_id=node_id,
                tenant_id=self._optional_string(arguments, "tenant_id"),
                user_id=self._optional_string(arguments, "user_id"),
                limit=limit,
            )
        elif layer == "fact":
            neighbors = self._fact_graph_neighbors(
                domain=domain,
                node_id=node_id,
                tenant_id=self._optional_string(arguments, "tenant_id"),
                user_id=self._optional_string(arguments, "user_id"),
                limit=limit,
            )
        else:
            raise ValueError("get_graph_neighbors currently supports fact, interpretation, and personal nodes only.")
        return {
            "status": "ok",
            "node_id": node_id,
            "layer": layer,
            "neighbors": neighbors[:limit],
        }

    def _get_dependency_impact(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        record_id = self._required_string(arguments, "record_id")
        record_type = self._required_string(arguments, "record_type").lower()
        if record_type == "fact":
            impact = self._dependency_impact_for_fact(domain=domain, record_id=record_id)
        elif record_type == "interpretation":
            impact = self._dependency_impact_for_interpretation(domain=domain, record_id=record_id)
        else:
            raise ValueError("record_type must be one of ['fact', 'interpretation'].")
        return {
            "status": "ok",
            "record_id": record_id,
            "record_type": record_type,
            "affected_interpretation_ids": impact["affected_interpretation_ids"],
            "affected_rendered_paths": impact["affected_rendered_paths"],
            "affected_personal_ids": impact["affected_personal_ids"],
        }

    def _get_job_status(self, arguments: dict[str, object]) -> dict[str, object]:
        job_id = self._required_string(arguments, "job_id")
        outbox_repository = self.bootstrap.outbox_repository
        if outbox_repository is None:
            raise ValueError("Outbox repository is not configured for this runtime.")
        event = outbox_repository.get_event(job_id)
        return {
            "status": "ok",
            "job": {
                "job_id": event["id"],
                "state": event["status"],
                "kind": self._job_kind(str(event["event_type"])),
                "event_type": event["event_type"],
                "aggregate_layer": event["aggregate_layer"],
                "aggregate_id": event["aggregate_id"],
                "attempt_count": event["attempt_count"],
                "available_at": event["available_at"],
                "claimed_at": event["claimed_at"],
                "processed_at": event["processed_at"],
                "last_error": event["last_error"],
                "payload": dict(event["payload"]),
            },
        }

    def _explain_result(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        result_id = self._required_string(arguments, "result_id")
        layer = arguments.get("layer")
        if layer is None:
            if isinstance(arguments.get("tenant_id"), str) and isinstance(arguments.get("user_id"), str):
                try:
                    return self._explain_personal_result(
                        domain=domain,
                        result_id=result_id,
                        tenant_id=self._required_string(arguments, "tenant_id"),
                        user_id=self._required_string(arguments, "user_id"),
                    )
                except KeyError:
                    pass
            return self._explain_interpretation_result(domain=domain, result_id=result_id)
        if not isinstance(layer, str) or not layer.strip():
            raise ValueError("layer must be a non-empty string when provided.")
        normalized_layer = layer.strip().lower()
        if normalized_layer == "interpretation":
            return self._explain_interpretation_result(domain=domain, result_id=result_id)
        if normalized_layer == "personal":
            return self._explain_personal_result(
                domain=domain,
                result_id=result_id,
                tenant_id=self._required_string(arguments, "tenant_id"),
                user_id=self._required_string(arguments, "user_id"),
            )
        raise ValueError("layer must be one of ['interpretation', 'personal'] when provided.")

    def _snapshot_layers(self, snapshot_status: dict[str, object]) -> dict[str, dict[str, object]]:
        raw_layers = snapshot_status.get("layers")
        if isinstance(raw_layers, dict):
            return {
                str(name): dict(status)
                for name, status in raw_layers.items()
                if isinstance(status, dict)
            }
        layer = snapshot_status.get("layer")
        if isinstance(layer, str):
            return {layer: dict(snapshot_status)}
        return {}

    def _current_cache_snapshots(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        snapshot_status: dict[str, object],
    ) -> dict[str, object]:
        layers = self._snapshot_layers(snapshot_status)
        fact_status = layers.get("fact")
        interpretation_status = layers.get("interpretation")
        current_snapshots: dict[str, object] = {
            **(
                {"fact_snapshot": fact_status["fact_snapshot_id"]}
                if fact_status is not None
                else {}
            ),
            **(
                {"interpretation_snapshot": interpretation_status["interpretation_snapshot_id"]}
                if interpretation_status is not None
                and "interpretation_snapshot_id" in interpretation_status
                else {}
            ),
        }
        try:
            profile_context = self.bootstrap.profile_context_repository.get_profile_context(
                domain,
                tenant_id,
                user_id,
            )
        except KeyError:
            profile_context = None
        if profile_context is not None and profile_context.get("profile_version"):
            current_snapshots["profile_version"] = profile_context["profile_version"]
        return current_snapshots

    def _personal_graph_neighbors(
        self,
        *,
        domain: str,
        node_id: str,
        tenant_id: str,
        user_id: str,
        limit: int,
    ) -> list[dict[str, object]]:
        scope_ref = {"scope": "user", "tenant_id": tenant_id, "user_id": user_id}
        records = self.bootstrap.personal_repository.get_by_ids([node_id], scope_ref)
        if not records or records[0].get("domain") != domain:
            raise KeyError(f"Unknown personal result {node_id!r} for domain {domain!r}.")
        record = dict(records[0])
        anchors = self._graph_anchor_refs(record)
        interpretation_ids = [
            anchor["id"]
            for anchor in anchors
            if anchor["layer"] == "interpretation"
        ]
        fact_ids = [
            anchor["id"]
            for anchor in anchors
            if anchor["layer"] == "fact"
        ]
        interpretation_records = self.bootstrap.interpretation_repository.get_by_ids(
            interpretation_ids,
            {"scope": "shared"},
        )
        fact_records = self.bootstrap.fact_repository.get_by_ids(
            fact_ids,
            {"scope": "shared"},
        )
        neighbors = [
            self._graph_neighbor_item(
                layer="interpretation",
                record=item,
                edge_type="anchored_to",
                direction="outgoing",
            )
            for item in interpretation_records
            if item.get("domain") == domain
        ]
        neighbors.extend(
            self._graph_neighbor_item(
                layer="fact",
                record=item,
                edge_type="anchored_to",
                direction="outgoing",
            )
            for item in fact_records
            if item.get("domain") == domain
        )
        return neighbors[:limit]

    def _interpretation_graph_neighbors(
        self,
        *,
        domain: str,
        node_id: str,
        tenant_id: str | None,
        user_id: str | None,
        limit: int,
    ) -> list[dict[str, object]]:
        record = self._require_shared_interpretation_record(domain=domain, interpretation_id=node_id)
        fact_ids = [
            fact_id
            for fact_id in self._result_anchor_ids(record)
            if fact_id.startswith("fact:")
        ]
        fact_records = self.bootstrap.fact_repository.get_by_ids(
            fact_ids,
            {"scope": "shared"},
        )
        neighbors = [
            self._graph_neighbor_item(
                layer="fact",
                record=item,
                edge_type="evidence_for",
                direction="outgoing",
            )
            for item in fact_records
            if item.get("domain") == domain
        ]
        if tenant_id is not None and user_id is not None:
            personal_records = self.bootstrap.personal_repository.search_by_anchors(
                domain=domain,
                scope_ref={"scope": "user", "tenant_id": tenant_id, "user_id": user_id},
                interpretation_ids=[node_id],
                fact_ids=[],
                limit=max(1, limit - len(neighbors)),
            )
            neighbors.extend(
                self._graph_neighbor_item(
                    layer="personal",
                    record=item,
                    edge_type="anchored_to",
                    direction="incoming",
                )
                for item in personal_records
            )
        return neighbors[:limit]

    def _fact_graph_neighbors(
        self,
        *,
        domain: str,
        node_id: str,
        tenant_id: str | None,
        user_id: str | None,
        limit: int,
    ) -> list[dict[str, object]]:
        fact_records = self.bootstrap.fact_repository.get_by_ids([node_id], {"scope": "shared"})
        if not fact_records or fact_records[0].get("domain") != domain:
            raise KeyError(f"Unknown fact node {node_id!r} for domain {domain!r}.")
        interpretation_records = self.bootstrap.interpretation_repository.list_records(
            domain=domain,
            scope_ref={"scope": "shared"},
            statuses=list(INTERPRETATION_LIFECYCLE_STATUSES),
            limit=max(limit * 4, 50),
        )
        neighbors = [
            self._graph_neighbor_item(
                layer="interpretation",
                record=item,
                edge_type="evidence_for",
                direction="incoming",
            )
            for item in interpretation_records
            if node_id in self._result_anchor_ids(item)
        ]
        if tenant_id is not None and user_id is not None:
            personal_records = self.bootstrap.personal_repository.search_by_anchors(
                domain=domain,
                scope_ref={"scope": "user", "tenant_id": tenant_id, "user_id": user_id},
                interpretation_ids=[],
                fact_ids=[node_id],
                limit=max(1, limit - len(neighbors)),
            )
            neighbors.extend(
                self._graph_neighbor_item(
                    layer="personal",
                    record=item,
                    edge_type="anchored_to",
                    direction="incoming",
                )
                for item in personal_records
        )
        return neighbors[:limit]

    def _dependency_impact_for_fact(
        self,
        *,
        domain: str,
        record_id: str,
    ) -> dict[str, object]:
        fact_records = self.bootstrap.fact_repository.get_by_ids([record_id], {"scope": "shared"})
        if not fact_records or fact_records[0].get("domain") != domain:
            raise KeyError(f"Unknown fact node {record_id!r} for domain {domain!r}.")
        interpretation_records = self.bootstrap.interpretation_repository.list_records(
            domain=domain,
            scope_ref={"scope": "shared"},
            statuses=list(INTERPRETATION_LIFECYCLE_STATUSES),
            limit=500,
        )
        affected_interpretations = [
            dict(record)
            for record in interpretation_records
            if record_id in self._result_anchor_ids(record)
        ]
        personal_records = self.bootstrap.personal_repository.search_by_anchors(
            domain=domain,
            scope_ref=None,
            interpretation_ids=[],
            fact_ids=[record_id],
            limit=500,
        )
        return {
            "affected_interpretation_ids": [str(record["id"]) for record in affected_interpretations],
            "affected_rendered_paths": self._rendered_paths_for_interpretations(affected_interpretations),
            "affected_personal_ids": [str(record["id"]) for record in personal_records],
        }

    def _dependency_impact_for_interpretation(
        self,
        *,
        domain: str,
        record_id: str,
    ) -> dict[str, object]:
        record = self._require_shared_interpretation_record(domain=domain, interpretation_id=record_id)
        personal_records = self.bootstrap.personal_repository.search_by_anchors(
            domain=domain,
            scope_ref=None,
            interpretation_ids=[record_id],
            fact_ids=[],
            limit=500,
        )
        return {
            "affected_interpretation_ids": [],
            "affected_rendered_paths": self._rendered_paths_for_interpretations([record]),
            "affected_personal_ids": [str(item["id"]) for item in personal_records],
        }

    def _explain_interpretation_result(
        self,
        *,
        domain: str,
        result_id: str,
    ) -> dict[str, object]:
        record = self._require_shared_interpretation_record(domain=domain, interpretation_id=result_id)
        snapshot_status = self.bootstrap.snapshot_repository.get_snapshot_status(domain=domain, layer=None)
        current_snapshots = self._shared_current_snapshots(snapshot_status)
        current_partition_records = self.bootstrap.interpretation_repository.list_records(
            domain=domain,
            scope_ref={"scope": "shared"},
            family=str(record.get("family") or ""),
            subject_id=str(record.get("subject_id") or ""),
            statuses=[INTERPRETATION_STATUS_PUBLISHED],
            limit=20,
        )
        current_partition_ids = [str(item["id"]) for item in current_partition_records]
        return {
            "status": "ok",
            "layer": "interpretation",
            "result_id": result_id,
            "explanation": {
                "based_on": self._interpretation_record_snapshots(record),
                "anchors": self._result_anchor_ids(record),
                "change_reason": self._interpretation_change_reason(
                    record=record,
                    current_snapshots=current_snapshots,
                    current_partition_ids=current_partition_ids,
                ),
                "lifecycle_state": record["status"],
                "review_state": self._proposal_review_state(str(record["status"])),
                "current_snapshots": current_snapshots,
                "current_partition_publication": {
                    "published_result_ids": current_partition_ids,
                },
                **({"provenance": dict(record["provenance"])} if isinstance(record.get("provenance"), dict) else {}),
            },
        }

    def _explain_personal_result(
        self,
        *,
        domain: str,
        result_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, object]:
        scope_ref = {"scope": "user", "tenant_id": tenant_id, "user_id": user_id}
        records = self.bootstrap.personal_repository.get_by_ids([result_id], scope_ref)
        if not records or records[0].get("domain") != domain:
            raise KeyError(f"Unknown personal result {result_id!r} for domain {domain!r}.")
        record = dict(records[0])
        snapshot_status = self.bootstrap.snapshot_repository.get_snapshot_status(domain=domain, layer=None)
        current_snapshots = (
            self._current_cache_snapshots(
                domain=domain,
                tenant_id=tenant_id,
                user_id=user_id,
                snapshot_status=snapshot_status,
            )
            if snapshot_status is not None
            else {}
        )
        record_snapshots = self._personal_record_snapshots(record)
        cache_state, reason = self._personal_cache_state(
            current_snapshots=current_snapshots,
            record_snapshots=record_snapshots,
        )
        return {
            "status": "ok",
            "layer": "personal",
            "result_id": result_id,
            "explanation": {
                "based_on": record_snapshots,
                "anchors": self._result_anchor_ids(record),
                "change_reason": reason if reason != "match" else "current_result",
                "cache_state": cache_state,
                "current_snapshots": current_snapshots,
                **({"provenance": dict(record["provenance"])} if isinstance(record.get("provenance"), dict) else {}),
            },
        }

    def _mark_personal_records_stale_for_interpretation_refresh(
        self,
        *,
        domain: str,
        publication: dict[str, object],
    ) -> list[str]:
        superseded_ids = [str(item) for item in publication.get("superseded_ids", []) if str(item)]
        if not superseded_ids:
            return []
        personal_records = self.bootstrap.personal_repository.search_by_anchors(
            domain=domain,
            scope_ref=None,
            interpretation_ids=superseded_ids,
            fact_ids=[],
            limit=500,
        )
        stale_ids: list[str] = []
        for record in personal_records:
            stale_ids.append(str(record["id"]))
            if str(record.get("status") or "") == "stale":
                continue
            updated = dict(record)
            updated["status"] = "stale"
            self.bootstrap.personal_repository.save_record(updated)
        stale_ids = self._dedupe_strings(stale_ids)
        if stale_ids and self.bootstrap.outbox_repository is not None:
            self.bootstrap.outbox_repository.append_events(
                [
                    self._build_personal_records_marked_stale_event(
                        domain=domain,
                        publication=publication,
                        superseded_ids=superseded_ids,
                        stale_ids=stale_ids,
                    )
                ]
            )
        return stale_ids

    def _require_interpretation_record(
        self,
        *,
        domain: str,
        proposal_id: str,
    ) -> dict[str, object]:
        records = self.bootstrap.interpretation_repository.get_by_ids(
            [proposal_id],
            {"scope": "shared"},
        )
        if not records or records[0].get("domain") != domain:
            raise KeyError(
                f"Unknown interpretation proposal {proposal_id!r} for domain {domain!r}."
            )
        return dict(records[0])

    def _require_shared_interpretation_record(
        self,
        *,
        domain: str,
        interpretation_id: str,
    ) -> dict[str, object]:
        records = self.bootstrap.interpretation_repository.get_by_ids(
            [interpretation_id],
            {"scope": "shared"},
        )
        if not records or records[0].get("domain") != domain:
            raise KeyError(
                f"Unknown interpretation result {interpretation_id!r} for domain {domain!r}."
            )
        return dict(records[0])

    def _proposal_summary(self, record: dict[str, object]) -> dict[str, object]:
        lifecycle_state = str(record["status"])
        return {
            "proposal_id": record["id"],
            "interpretation_id": record["id"],
            "lifecycle_state": lifecycle_state,
            "review_state": self._proposal_review_state(lifecycle_state),
            "family": record.get("family"),
            "kind": record.get("kind"),
            "subject_type": record.get("subject_type"),
            "subject_id": record.get("subject_id"),
            "title": record.get("title"),
            "summary": record.get("summary"),
            "computed_at": record.get("computed_at"),
        }

    def _build_personal_records_marked_stale_event(
        self,
        *,
        domain: str,
        publication: dict[str, object],
        superseded_ids: list[str],
        stale_ids: list[str],
    ) -> dict[str, object]:
        record = dict(publication["record"])
        outbox_event_ids = [str(item) for item in publication.get("outbox_event_ids", []) if str(item)]
        return {
            "event_type": "personal_records_marked_stale",
            "aggregate_layer": "personal",
            "aggregate_id": stale_ids[0],
            "payload": {
                "domain": domain,
                "fact_snapshot_id": record["fact_snapshot_id"],
                "interpretation_snapshot_id": record["interpretation_snapshot_id"],
                "personal_record_ids": stale_ids,
                "triggering_interpretation_ids": superseded_ids,
                "source_event_id": outbox_event_ids[0] if outbox_event_ids else record["id"],
                "scope": record["scope_ref"]["scope"],
            },
        }

    def _proposal_review_state(self, lifecycle_state: str) -> str:
        if lifecycle_state == INTERPRETATION_STATUS_PROPOSED:
            return "pending_validation"
        if lifecycle_state == INTERPRETATION_STATUS_VALIDATED:
            return "ready_to_publish"
        if lifecycle_state == INTERPRETATION_STATUS_PUBLISHED:
            return "published"
        if lifecycle_state == INTERPRETATION_STATUS_STALE:
            return "refresh_recommended"
        if lifecycle_state == INTERPRETATION_STATUS_SUPERSEDED:
            return "superseded"
        if lifecycle_state == INTERPRETATION_STATUS_REJECTED:
            return "rejected"
        return "unknown"

    def _required_interpretation_partition(
        self,
        arguments: dict[str, object],
    ) -> dict[str, str]:
        partition = self._optional_interpretation_partition(arguments)
        if partition is None:
            raise ValueError("Missing required interpretation partition.")
        return partition

    def _optional_interpretation_partition(
        self,
        arguments: dict[str, object],
    ) -> dict[str, str] | None:
        partition = arguments.get("partition")
        if partition is None:
            return None
        if not isinstance(partition, dict):
            raise ValueError("partition must be an object when provided.")
        return {
            "family": self._normalize_family(self._required_string(partition, "family")),
            "subject_id": self._required_string(
                partition,
                "segment",
                fallback_key="subject_id",
            ),
        }

    def _shared_current_snapshots(
        self,
        snapshot_status: dict[str, object] | None,
    ) -> dict[str, object]:
        if snapshot_status is None:
            return {}
        layers = self._snapshot_layers(snapshot_status)
        fact_status = layers.get("fact")
        interpretation_status = layers.get("interpretation")
        return {
            **(
                {"fact_snapshot": fact_status["fact_snapshot_id"]}
                if fact_status is not None
                else {}
            ),
            **(
                {"interpretation_snapshot": interpretation_status["interpretation_snapshot_id"]}
                if interpretation_status is not None
                and "interpretation_snapshot_id" in interpretation_status
                else {}
            ),
        }

    def _interpretation_record_snapshots(
        self,
        record: dict[str, object],
    ) -> dict[str, object]:
        return {
            "fact_snapshot": record.get("fact_snapshot_id"),
            **(
                {"interpretation_snapshot": record.get("interpretation_snapshot_id")}
                if record.get("interpretation_snapshot_id")
                else {}
            ),
        }

    def _personal_record_snapshots(
        self,
        record: dict[str, object],
    ) -> dict[str, object]:
        record_snapshot_ref = dict(record.get("snapshot_ref") or {})
        return {
            "fact_snapshot": record_snapshot_ref.get("fact_snapshot_id"),
            **(
                {"interpretation_snapshot": record_snapshot_ref.get("interpretation_snapshot_id")}
                if record_snapshot_ref.get("interpretation_snapshot_id")
                else {}
            ),
            **(
                {"profile_version": record_snapshot_ref.get("profile_version") or record.get("profile_version")}
                if (record_snapshot_ref.get("profile_version") or record.get("profile_version"))
                else {}
            ),
        }

    def _personal_cache_state(
        self,
        *,
        current_snapshots: dict[str, object],
        record_snapshots: dict[str, object],
    ) -> tuple[str, str]:
        if (
            current_snapshots.get("profile_version")
            and record_snapshots.get("profile_version") != current_snapshots.get("profile_version")
        ):
            return "invalid", "profile_version_changed"
        if (
            current_snapshots.get("interpretation_snapshot")
            and record_snapshots.get("interpretation_snapshot") != current_snapshots.get("interpretation_snapshot")
        ):
            return "stale", "interpretation_snapshot_changed"
        if (
            current_snapshots.get("fact_snapshot")
            and record_snapshots.get("fact_snapshot") != current_snapshots.get("fact_snapshot")
        ):
            return "stale", "fact_snapshot_changed"
        return "fresh", "match"

    def _interpretation_change_reason(
        self,
        *,
        record: dict[str, object],
        current_snapshots: dict[str, object],
        current_partition_ids: list[str],
    ) -> str:
        lifecycle_state = str(record["status"])
        if lifecycle_state == INTERPRETATION_STATUS_PROPOSED:
            return "proposal_pending_validation"
        if lifecycle_state == INTERPRETATION_STATUS_VALIDATED:
            return "validated_waiting_for_publication"
        if lifecycle_state == INTERPRETATION_STATUS_REJECTED:
            return "proposal_rejected"
        if lifecycle_state == INTERPRETATION_STATUS_STALE:
            return "marked_stale"
        if lifecycle_state == INTERPRETATION_STATUS_SUPERSEDED:
            return "superseded"
        if (
            current_partition_ids
            and str(record["id"]) not in current_partition_ids
            and lifecycle_state == INTERPRETATION_STATUS_PUBLISHED
        ):
            return "superseded_by_partition_publication"
        if (
            current_snapshots.get("interpretation_snapshot")
            and record.get("interpretation_snapshot_id") != current_snapshots.get("interpretation_snapshot")
        ):
            return "new_interpretation_snapshot"
        if (
            current_snapshots.get("fact_snapshot")
            and record.get("fact_snapshot_id") != current_snapshots.get("fact_snapshot")
        ):
            return "new_fact_snapshot"
        return "current_result"

    def _result_anchor_ids(self, record: dict[str, object]) -> list[str]:
        anchors: list[str] = []
        seen: set[str] = set()
        for anchor in self._graph_anchor_refs(record):
            normalized = anchor["id"]
            if normalized not in seen:
                anchors.append(normalized)
                seen.add(normalized)
        evidence = record.get("evidence")
        if isinstance(evidence, list):
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                fact_id = item.get("fact_id")
                if not isinstance(fact_id, str) or not fact_id.strip():
                    continue
                normalized = fact_id.strip()
                if normalized not in seen:
                    anchors.append(normalized)
                    seen.add(normalized)
        return anchors

    def _graph_anchor_refs(self, record: dict[str, object]) -> list[dict[str, str]]:
        raw_anchors = record.get("anchors")
        if not isinstance(raw_anchors, list):
            body = record.get("body")
            if isinstance(body, dict) and isinstance(body.get("anchors"), list):
                raw_anchors = body.get("anchors")
        anchors: list[dict[str, str]] = []
        if not isinstance(raw_anchors, list):
            return anchors
        for anchor in raw_anchors:
            if not isinstance(anchor, dict):
                continue
            layer = anchor.get("layer")
            anchor_id = anchor.get("id")
            if not isinstance(layer, str) or not layer.strip():
                continue
            if not isinstance(anchor_id, str) or not anchor_id.strip():
                continue
            anchors.append({"layer": layer.strip(), "id": anchor_id.strip()})
        return anchors

    def _graph_neighbor_item(
        self,
        *,
        layer: str,
        record: dict[str, object],
        edge_type: str,
        direction: str,
    ) -> dict[str, object]:
        return {
            "node_id": record["id"],
            "layer": layer,
            "edge_type": edge_type,
            "direction": direction,
            **({"title": self._graph_record_title(layer, record)} if self._graph_record_title(layer, record) else {}),
            **({"summary": self._graph_record_summary(layer, record)} if self._graph_record_summary(layer, record) else {}),
        }

    def _graph_record_title(self, layer: str, record: dict[str, object]) -> str:
        if layer == "fact":
            attributes = record.get("attributes")
            if isinstance(attributes, dict):
                title = attributes.get("title") or attributes.get("name") or attributes.get("label")
                if isinstance(title, str) and title.strip():
                    return title.strip()
        title = record.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        return ""

    def _graph_record_summary(self, layer: str, record: dict[str, object]) -> str:
        if layer == "fact":
            attributes = record.get("attributes")
            if isinstance(attributes, dict):
                summary = attributes.get("summary") or attributes.get("description")
                if isinstance(summary, str) and summary.strip():
                    return summary.strip()
        summary = record.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
        return ""

    def _graph_node_layer(self, arguments: dict[str, object], *, node_id: str) -> str:
        explicit = self._optional_string(arguments, "layer")
        if explicit is not None:
            return explicit.lower()
        if node_id.startswith("fact:"):
            return "fact"
        if node_id.startswith("interp:"):
            return "interpretation"
        if node_id.startswith("personal:"):
            return "personal"
        raise ValueError("Unable to infer graph node layer from node_id; provide layer explicitly.")

    def _rendered_paths_for_interpretations(
        self,
        records: list[dict[str, object]],
    ) -> list[str]:
        paths: list[str] = []
        for record in records:
            path = self._rendered_path_for_interpretation(record)
            if path is not None:
                paths.append(path)
        return self._dedupe_strings(paths)

    def _rendered_path_for_interpretation(
        self,
        record: dict[str, object],
    ) -> str | None:
        render_hints = record.get("render_hints")
        if not isinstance(render_hints, dict):
            return None
        family = render_hints.get("page_family") or record.get("family")
        key = render_hints.get("page_key") or record.get("subject_id")
        if not isinstance(family, str) or not family.strip():
            return None
        if not isinstance(key, str) or not key.strip():
            return None
        return f"wiki/shared/interpretations/{family.strip()}/{key.strip()}.md"

    def _job_kind(self, event_type: str) -> str:
        if event_type == "interpretation_snapshot_build_requested":
            return "interpretation_build"
        if event_type == "interpretation_snapshot_published":
            return "interpretation_publish"
        if event_type == "fact_ingested":
            return "fact_ingest"
        return event_type

    def _interpretation_status(self, value: object, *, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing required interpretation status: {field}")
        normalized = value.strip().lower()
        if normalized not in INTERPRETATION_LIFECYCLE_STATUSES:
            raise ValueError(
                f"{field} must be one of {list(INTERPRETATION_LIFECYCLE_STATUSES)}."
            )
        return normalized

    def _optional_limit(self, arguments: dict[str, object], *, default: int) -> int:
        value = arguments.get("limit")
        if value is None:
            return default
        if not isinstance(value, int) or value <= 0:
            raise ValueError("limit must be a positive integer when provided.")
        return value

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

    def _optional_string(self, arguments: dict[str, object], key: str) -> str | None:
        value = arguments.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string when provided.")
        return value.strip()

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if value in seen:
                continue
            ordered.append(value)
            seen.add(value)
        return ordered

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

    def _parse_profile_context(self, arguments: dict[str, object]) -> dict[str, Any]:
        goals = arguments.get("goals")
        preferences = arguments.get("preferences")
        attributes = arguments.get("attributes")
        if not isinstance(goals, list) or not all(isinstance(goal, str) for goal in goals):
            raise ValueError("Profile context goals must be a list of strings.")
        if not isinstance(preferences, dict):
            raise ValueError("Profile context preferences must be an object.")
        if not isinstance(attributes, dict):
            raise ValueError("Profile context attributes must be an object.")
        return {
            "domain": self._required_string(arguments, "domain"),
            "tenant_id": self._required_string(arguments, "tenant_id"),
            "user_id": self._required_string(arguments, "user_id"),
            "profile_version": self._required_string(arguments, "profile_version"),
            "goals": [goal.strip() for goal in goals],
            "preferences": dict(preferences),
            "attributes": dict(attributes),
        }


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
