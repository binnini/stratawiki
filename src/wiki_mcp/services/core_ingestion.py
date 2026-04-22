from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.ingestion_batch import IngestionBatch
from wiki_mcp.schemas.ingestion_result import IngestionResult
from wiki_mcp.schemas.outbox_event import OutboxEvent
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.schemas.validation_result import ValidationResult
from wiki_mcp.services.interfaces.domain_ingestion import DomainIngestionPlugin
from wiki_mcp.services.interfaces.repositories import (
    FactRepository,
    OutboxRepository,
    SnapshotRepository,
)


class DefaultCoreIngestionService:
    """Canonical Fact write service with a legacy source/plugin compatibility seam.

    `ingest_batch` is the preferred shared persistence primitive used by the
    proposal gateway. The `SourceRecord -> DomainIngestionPlugin` entrypoints
    remain available for internal transition and compatibility flows.
    """

    def __init__(
        self,
        *,
        fact_repository: FactRepository,
        snapshot_repository: SnapshotRepository,
        outbox_repository: OutboxRepository,
    ) -> None:
        self.fact_repository = fact_repository
        self.snapshot_repository = snapshot_repository
        self.outbox_repository = outbox_repository

    def prepare_legacy_source_batch(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionBatch:
        if not plugin.accepts(source):
            raise ValueError(
                f"Plugin {plugin.__class__.__name__} does not accept source domain {source['domain']!r}."
            )

        normalized = plugin.normalize_source(source)
        records = plugin.extract_fact_records(normalized)
        relations = plugin.extract_fact_relations(normalized, records)
        validation = plugin.validate_batch(normalized, records, relations)
        validation = self._merge_validation(
            validation,
            self._validate_scope_shapes(records, relations),
            self._validate_canonical_identity(records),
            self._validate_relation_targets(records, relations),
        )

        return {
            "source": normalized,
            "records": records,
            "relations": relations,
            "validation": validation,
        }

    def prepare_batch(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionBatch:
        return self.prepare_legacy_source_batch(source, plugin)

    def ingest_batch(self, batch: IngestionBatch) -> IngestionResult:
        validation = batch["validation"]
        if not validation["ok"]:
            raise ValueError(
                "Cannot ingest invalid batch: " + "; ".join(validation["errors"])
            )

        fact_snapshot_id = self._new_fact_snapshot_id(batch["source"])
        write_result = self.fact_repository.write_facts(
            batch["records"],
            batch["relations"],
            fact_snapshot_id=fact_snapshot_id,
        )
        self.snapshot_repository.publish_snapshot(
            "fact",
            batch["source"]["domain"],
            {"fact_snapshot_id": fact_snapshot_id},
        )
        outbox_event_ids = self.outbox_repository.append_events(
            [self._build_fact_ingested_event(batch, write_result, fact_snapshot_id)]
        )

        return {
            "fact_snapshot_id": fact_snapshot_id,
            "facts_created": write_result["facts_created"],
            "facts_updated": write_result["facts_updated"],
            "relations_created": write_result["relations_created"],
            "affected_fact_ids": write_result["affected_fact_ids"],
            "outbox_event_ids": outbox_event_ids,
        }

    def ingest_legacy_source(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionResult:
        batch = self.prepare_legacy_source_batch(source, plugin)
        return self.ingest_batch(batch)

    def ingest_source(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionResult:
        return self.ingest_legacy_source(source, plugin)

    def _validate_scope_shapes(
        self,
        records: list[FactRecord],
        relations: list[FactRelation],
    ) -> ValidationResult:
        errors: list[str] = []

        for index, record in enumerate(records, start=1):
            self._append_scope_shape_errors(
                errors,
                record["scope"],
                record.get("tenant_id"),
                record.get("user_id"),
                f"record[{index}] {record['id']}",
            )

        for index, relation in enumerate(relations, start=1):
            self._append_scope_shape_errors(
                errors,
                relation["scope"],
                relation.get("tenant_id"),
                relation.get("user_id"),
                f"relation[{index}] {relation['relation_type']}",
            )

        return {
            "ok": len(errors) == 0,
            "warnings": [],
            "errors": errors,
        }

    def _validate_relation_targets(
        self,
        records: list[FactRecord],
        relations: list[FactRelation],
    ) -> ValidationResult:
        canonical_keys = {record["canonical_key"] for record in records}
        errors: list[str] = []

        for relation in relations:
            if relation["from_canonical_key"] not in canonical_keys:
                errors.append(
                    f"Relation {relation['relation_type']!r} references missing from_canonical_key "
                    f"{relation['from_canonical_key']!r}."
                )
            if relation["to_canonical_key"] not in canonical_keys:
                errors.append(
                    f"Relation {relation['relation_type']!r} references missing to_canonical_key "
                    f"{relation['to_canonical_key']!r}."
                )

        return {
            "ok": len(errors) == 0,
            "warnings": [],
            "errors": errors,
        }

    def _validate_canonical_identity(
        self,
        records: list[FactRecord],
    ) -> ValidationResult:
        seen_keys: dict[tuple[str, str, str | None, str | None], str] = {}
        errors: list[str] = []

        for record in records:
            identity = (
                record["scope"],
                record["canonical_key"],
                record.get("tenant_id"),
                record.get("user_id"),
            )
            existing_id = seen_keys.get(identity)
            if existing_id is not None and existing_id != record["id"]:
                errors.append(
                    "Duplicate canonical Fact identity in batch for "
                    f"{record['canonical_key']!r} with scope {record['scope']!r}: "
                    f"{existing_id!r} and {record['id']!r}."
                )
                continue

            seen_keys[identity] = record["id"]

        return {
            "ok": len(errors) == 0,
            "warnings": [],
            "errors": errors,
        }

    def _merge_validation(
        self,
        *results: ValidationResult,
    ) -> ValidationResult:
        warnings: list[str] = []
        errors: list[str] = []
        for result in results:
            warnings.extend(result["warnings"])
            errors.extend(result["errors"])

        return {
            "ok": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
        }

    def _append_scope_shape_errors(
        self,
        errors: list[str],
        scope: str,
        tenant_id: str | None,
        user_id: str | None,
        label: str,
    ) -> None:
        if scope not in {"shared", "tenant", "user"}:
            errors.append(f"{label} has unsupported scope {scope!r}.")
            return

        if scope == "shared" and (tenant_id is not None or user_id is not None):
            errors.append(f"{label} uses shared scope but still carries tenant/user identifiers.")
        elif scope == "tenant" and (tenant_id is None or user_id is not None):
            errors.append(
                f"{label} uses tenant scope but must include tenant_id and omit user_id."
            )
        elif scope == "user" and (tenant_id is None or user_id is None):
            errors.append(
                f"{label} uses user scope but must include both tenant_id and user_id."
            )

    def _new_fact_snapshot_id(self, source: SourceRecord) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"fact_snap:{source['domain']}:{source['source_id']}:{timestamp}:{uuid4().hex[:8]}"

    def _build_fact_ingested_event(
        self,
        batch: IngestionBatch,
        write_result: dict[str, object],
        fact_snapshot_id: str,
    ) -> OutboxEvent:
        source = batch["source"]
        return {
            "event_type": "fact_ingested",
            "aggregate_layer": "fact",
            "aggregate_id": fact_snapshot_id,
            "idempotency_key": f"fact_ingested:{fact_snapshot_id}",
            "payload": {
                "domain": source["domain"],
                "source_id": source["source_id"],
                "connector": source["connector"],
                "fact_snapshot_id": fact_snapshot_id,
                "affected_fact_ids": write_result["affected_fact_ids"],
                "affected_entity_types": [
                    record["entity_type"] for record in batch["records"]
                ],
                "scope": batch["records"][0]["scope"] if batch["records"] else "shared",
                **(
                    {"tenant_id": batch["records"][0]["tenant_id"]}
                    if batch["records"] and "tenant_id" in batch["records"][0]
                    else {}
                ),
                **(
                    {"user_id": batch["records"][0]["user_id"]}
                    if batch["records"] and "user_id" in batch["records"][0]
                    else {}
                ),
                "facts_created": write_result["facts_created"],
                "facts_updated": write_result["facts_updated"],
                "relations_created": write_result["relations_created"],
            },
        }
