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

        return {
            "status": "ok" if not failures else "partial",
            "source_state": source_state,
            "published_records": len(published_proposal_ids),
            "published_proposal_ids": published_proposal_ids,
            **({"interpretation_snapshot": interpretation_snapshot} if interpretation_snapshot else {}),
            "superseded_ids": superseded_ids,
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
        record_snapshot_ref = dict(record.get("snapshot_ref") or {})
        record_snapshots = {
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

        cache_state = "fresh"
        reason = "match"
        if (
            current_snapshots.get("profile_version")
            and record_snapshots.get("profile_version") != current_snapshots.get("profile_version")
        ):
            cache_state = "invalid"
            reason = "profile_version_changed"
        elif (
            current_snapshots.get("interpretation_snapshot")
            and record_snapshots.get("interpretation_snapshot") != current_snapshots.get("interpretation_snapshot")
        ):
            cache_state = "stale"
            reason = "interpretation_snapshot_changed"
        elif (
            current_snapshots.get("fact_snapshot")
            and record_snapshots.get("fact_snapshot") != current_snapshots.get("fact_snapshot")
        ):
            cache_state = "stale"
            reason = "fact_snapshot_changed"

        return {
            "status": "ok",
            "record_id": record_id,
            "cache_state": cache_state,
            "reason": reason,
            "current_snapshots": current_snapshots,
            "record_snapshots": record_snapshots,
        }

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
