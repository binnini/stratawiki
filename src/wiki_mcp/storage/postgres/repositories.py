from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from wiki_mcp.schemas.dependency_impact import DependencyImpact
from wiki_mcp.schemas.dependency_edge import DependencyEdge
from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.fact_write_result import FactWriteResult
from wiki_mcp.schemas.interpretation_record import (
    InterpretationRecord,
    interpretation_payload,
    interpretation_support_links,
    materialize_interpretation_record,
)
from wiki_mcp.schemas.metadata_validation import (
    ensure_interpretation_status,
    ensure_non_empty_string,
    ensure_personal_anchors,
    ensure_provenance,
    ensure_scope_ref,
    ensure_scope_shape,
    ensure_snapshot_ref,
)
from wiki_mcp.schemas.outbox_event import OutboxEvent, OutboxEventRecord
from wiki_mcp.schemas.personal_asset import PersonalAssetRecord
from wiki_mcp.schemas.personal_record import PersonalRecord
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.storage.postgres.base import PostgresRepositoryBase, managed_cursor
from wiki_mcp.services.personal_assets import PersonalAssetConflictError


def _normalized_text_sql(*parts: str) -> str:
    joined = ", ".join(f"COALESCE({part}, '')" for part in parts)
    return (
        "regexp_replace(lower(concat_ws(' ', "
        + joined
        + ")), '[^a-z0-9]+', ' ', 'g')"
    )


def _fts_query_sql(
    *,
    query_text: str,
    query_tokens: list[str] | None = None,
) -> tuple[str, list[Any]]:
    normalized_tokens = [token for token in (query_tokens or []) if token]
    if normalized_tokens:
        return "to_tsquery('simple', %s)", [" | ".join(normalized_tokens)]
    return "websearch_to_tsquery('simple', %s)", [query_text]


def _fts_vector_sql(
    *,
    search_expr: str,
) -> str:
    return f"to_tsvector('simple', {search_expr})"


class PostgresFactRepository(PostgresRepositoryBase):
    """Persist generic fact envelopes into early Postgres staging tables."""

    def get_by_canonical_keys(
        self,
        canonical_keys: list[str],
        scope_ref: ScopeRef,
    ) -> list[FactRecord]:
        if not canonical_keys:
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref, table_alias="r")
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    layer,
                    domain,
                    entity_type,
                    canonical_key,
                    scope,
                    fact_snapshot_id,
                    tenant_id,
                    user_id,
                    status,
                    version,
                    created_at,
                    updated_at,
                    schema_version,
                    attributes_json,
                    provenance_json
                FROM fact.record_envelopes
                WHERE canonical_key = ANY(%s) AND {scope_sql}
                """,
                [canonical_keys, *scope_params],
            )
            return [self._row_to_fact_record(row) for row in cursor.fetchall()]

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: ScopeRef,
    ) -> list[FactRecord]:
        if not ids:
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    layer,
                    domain,
                    entity_type,
                    canonical_key,
                    scope,
                    fact_snapshot_id,
                    tenant_id,
                    user_id,
                    status,
                    version,
                    created_at,
                    updated_at,
                    schema_version,
                    attributes_json,
                    provenance_json
                FROM fact.record_envelopes
                WHERE id = ANY(%s) AND {scope_sql}
                """,
                [ids, *scope_params],
            )
            return [self._row_to_fact_record(row) for row in cursor.fetchall()]

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[FactRecord]:
        if limit <= 0 or (not query_text and not query_tokens):
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        search_expr = _normalized_text_sql(
            "id",
            "entity_type",
            "canonical_key",
            "attributes_json->>'title'",
            "attributes_json->>'name'",
            "attributes_json->>'label'",
            "attributes_json->>'summary'",
            "attributes_json->>'description'",
            "attributes_json->>'headline'",
        )
        vector_sql = _fts_vector_sql(search_expr=search_expr)
        query_sql, query_params = _fts_query_sql(
            query_text=query_text,
            query_tokens=query_tokens,
        )
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    layer,
                    domain,
                    entity_type,
                    canonical_key,
                    scope,
                    fact_snapshot_id,
                    tenant_id,
                    user_id,
                    status,
                    version,
                    created_at,
                    updated_at,
                    schema_version,
                    attributes_json,
                    provenance_json
                FROM fact.record_envelopes
                WHERE domain = %s AND {scope_sql} AND {vector_sql} @@ {query_sql}
                ORDER BY ts_rank_cd({vector_sql}, {query_sql}) DESC, updated_at DESC, id ASC
                LIMIT %s
                """,
                [domain, *scope_params, *query_params, *query_params, limit],
            )
            return [self._row_to_fact_record(row) for row in cursor.fetchall()]

    def list_records(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        entity_type: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 200,
    ) -> list[FactRecord]:
        if limit <= 0:
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        filters = ["domain = %s", scope_sql]
        params: list[Any] = [domain, *scope_params]

        if entity_type is not None:
            filters.append("entity_type = %s")
            params.append(entity_type)
        if statuses:
            filters.append("status = ANY(%s)")
            params.append(statuses)
        params.append(limit)

        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    layer,
                    domain,
                    entity_type,
                    canonical_key,
                    scope,
                    fact_snapshot_id,
                    tenant_id,
                    user_id,
                    status,
                    version,
                    created_at,
                    updated_at,
                    schema_version,
                    attributes_json,
                    provenance_json
                FROM fact.record_envelopes
                WHERE {" AND ".join(filters)}
                ORDER BY updated_at DESC, id ASC
                LIMIT %s
                """,
                params,
            )
            return [self._row_to_fact_record(row) for row in cursor.fetchall()]

    def list_relations(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        relation_types: list[str] | None = None,
        limit: int = 500,
    ) -> list[FactRelation]:
        if limit <= 0:
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        filters = ["domain = %s", scope_sql]
        params: list[Any] = [domain, *scope_params]

        if relation_types:
            filters.append("relation_type = ANY(%s)")
            params.append(relation_types)
        params.append(limit)

        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    domain,
                    relation_type,
                    from_canonical_key,
                    to_canonical_key,
                    scope,
                    tenant_id,
                    user_id,
                    schema_version,
                    provenance_json,
                    attributes_json
                FROM fact.relation_envelopes
                WHERE {" AND ".join(filters)}
                ORDER BY relation_type ASC, from_canonical_key ASC, to_canonical_key ASC
                LIMIT %s
                """,
                params,
            )
            return [self._row_to_fact_relation(row) for row in cursor.fetchall()]

    def write_facts(
        self,
        records: list[FactRecord],
        relations: list[FactRelation],
        *,
        fact_snapshot_id: str,
    ) -> FactWriteResult:
        ensure_non_empty_string(fact_snapshot_id, label="fact_snapshot_id")
        facts_created = 0
        facts_updated = 0
        relations_created = 0
        affected_fact_ids: list[str] = []

        with managed_cursor(self.connection) as cursor:
            prepared_records = [
                self._prepare_fact_record_for_write(
                    cursor=cursor,
                    record=record,
                    fact_snapshot_id=fact_snapshot_id,
                )
                for record in records
            ]

            for record in prepared_records:
                cursor.execute(
                    """
                    INSERT INTO fact.record_envelopes (
                        id,
                        layer,
                        domain,
                        entity_type,
                        canonical_key,
                        scope,
                        fact_snapshot_id,
                        tenant_id,
                        user_id,
                        status,
                        version,
                        created_at,
                        updated_at,
                        schema_version,
                        attributes_json,
                        provenance_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        layer = EXCLUDED.layer,
                        domain = EXCLUDED.domain,
                        entity_type = EXCLUDED.entity_type,
                        canonical_key = EXCLUDED.canonical_key,
                        scope = EXCLUDED.scope,
                        fact_snapshot_id = EXCLUDED.fact_snapshot_id,
                        tenant_id = EXCLUDED.tenant_id,
                        user_id = EXCLUDED.user_id,
                        status = EXCLUDED.status,
                        version = EXCLUDED.version,
                        updated_at = EXCLUDED.updated_at,
                        schema_version = EXCLUDED.schema_version,
                        attributes_json = EXCLUDED.attributes_json,
                        provenance_json = EXCLUDED.provenance_json
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (
                        record["id"],
                        record["layer"],
                        record["domain"],
                        record["entity_type"],
                        record["canonical_key"],
                        record["scope"],
                        fact_snapshot_id,
                        record.get("tenant_id"),
                        record.get("user_id"),
                        record["status"],
                        record["version"],
                        record["created_at"],
                        record["updated_at"],
                        record["schema_version"],
                        self._json(record["attributes"]),
                        self._json(record["provenance"]),
                    ),
                )
                row = cursor.fetchone()
                inserted = bool(self._row_to_dict(row)["inserted"])
                facts_created += 1 if inserted else 0
                facts_updated += 0 if inserted else 1
                affected_fact_ids.append(record["id"])

            for relation in relations:
                self._validate_fact_relation(relation)
                cursor.execute(
                    """
                    INSERT INTO fact.relation_envelopes (
                        domain,
                        relation_type,
                        from_canonical_key,
                        to_canonical_key,
                        scope,
                        tenant_id,
                        user_id,
                        schema_version,
                        provenance_json,
                        attributes_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        relation["domain"],
                        relation["relation_type"],
                        relation["from_canonical_key"],
                        relation["to_canonical_key"],
                        relation["scope"],
                        relation.get("tenant_id"),
                        relation.get("user_id"),
                        relation["schema_version"],
                        self._json(relation["provenance"]),
                        self._json(relation.get("attributes", {})),
                    ),
                )
                relations_created += cursor.rowcount

        return {
            "facts_created": facts_created,
            "facts_updated": facts_updated,
            "relations_created": relations_created,
            "affected_fact_ids": affected_fact_ids,
        }

    def _prepare_fact_record_for_write(
        self,
        *,
        cursor: Any,
        record: FactRecord,
        fact_snapshot_id: str,
    ) -> FactRecord:
        self._validate_fact_record(record, fact_snapshot_id=fact_snapshot_id)

        existing_by_id = self._load_existing_fact_by_id(cursor=cursor, record_id=record["id"])
        existing_by_key = self._load_existing_fact_by_canonical_identity(
            cursor=cursor,
            canonical_key=record["canonical_key"],
            scope_ref=self._scope_ref_for_fact(record),
        )
        if existing_by_key is not None and existing_by_key["id"] != record["id"]:
            raise ValueError(
                "Canonical Fact identity conflict at storage boundary for "
                f"{record['canonical_key']!r}: existing id {existing_by_key['id']!r}, "
                f"incoming id {record['id']!r}."
            )

        timestamp = self._now_timestamp()
        current = existing_by_id or existing_by_key
        created_at = str(record.get("created_at") or (current or {}).get("created_at") or timestamp)
        version = int(record.get("version") or (current or {}).get("version") or 0) + (
            0 if "version" in record else 1
        )
        if current is None and "version" not in record:
            version = 1

        normalized = dict(record)
        normalized["layer"] = "fact"
        normalized["fact_snapshot_id"] = fact_snapshot_id
        normalized["status"] = str(record.get("status") or (current or {}).get("status") or "active")
        normalized["version"] = version
        normalized["created_at"] = created_at
        normalized["updated_at"] = str(record.get("updated_at") or timestamp)
        return normalized  # type: ignore[return-value]

    def _load_existing_fact_by_id(
        self,
        *,
        cursor: Any,
        record_id: str,
    ) -> FactRecord | None:
        cursor.execute(
            """
            SELECT
                id,
                layer,
                domain,
                entity_type,
                canonical_key,
                scope,
                fact_snapshot_id,
                tenant_id,
                user_id,
                status,
                version,
                created_at,
                updated_at,
                schema_version,
                attributes_json,
                provenance_json
            FROM fact.record_envelopes
            WHERE id = %s
            """,
            [record_id],
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_fact_record(row)

    def _load_existing_fact_by_canonical_identity(
        self,
        *,
        cursor: Any,
        canonical_key: str,
        scope_ref: ScopeRef,
    ) -> FactRecord | None:
        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        cursor.execute(
            f"""
            SELECT
                id,
                layer,
                domain,
                entity_type,
                canonical_key,
                scope,
                fact_snapshot_id,
                tenant_id,
                user_id,
                status,
                version,
                created_at,
                updated_at,
                schema_version,
                attributes_json,
                provenance_json
            FROM fact.record_envelopes
            WHERE canonical_key = %s AND {scope_sql}
            ORDER BY updated_at DESC, id ASC
            LIMIT 1
            """,
            [canonical_key, *scope_params],
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_fact_record(row)

    def _scope_ref_for_fact(self, record: FactRecord) -> ScopeRef:
        scope_ref: ScopeRef = {"scope": record["scope"]}
        if record.get("tenant_id") is not None:
            scope_ref["tenant_id"] = record["tenant_id"]
        if record.get("user_id") is not None:
            scope_ref["user_id"] = record["user_id"]
        return scope_ref

    def _now_timestamp(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _row_to_fact_record(self, row: Any) -> FactRecord:
        data = self._row_to_dict(row)
        return {
            "id": data["id"],
            "layer": str(data.get("layer") or "fact"),
            "domain": data["domain"],
            "entity_type": data["entity_type"],
            "canonical_key": data["canonical_key"],
            "attributes": self._load_json(data["attributes_json"]),
            "scope": data["scope"],
            **(
                {"fact_snapshot_id": data["fact_snapshot_id"]}
                if data.get("fact_snapshot_id")
                else {}
            ),
            **({"tenant_id": data["tenant_id"]} if data.get("tenant_id") else {}),
            **({"user_id": data["user_id"]} if data.get("user_id") else {}),
            "status": str(data.get("status") or "active"),
            "version": int(data.get("version") or 1),
            **({"created_at": str(data["created_at"])} if data.get("created_at") else {}),
            **({"updated_at": str(data["updated_at"])} if data.get("updated_at") else {}),
            "schema_version": data["schema_version"],
            "provenance": self._load_json(data["provenance_json"]),
        }

    def _row_to_fact_relation(self, row: Any) -> FactRelation:
        data = self._row_to_dict(row)
        return {
            "domain": data["domain"],
            "relation_type": data["relation_type"],
            "from_canonical_key": data["from_canonical_key"],
            "to_canonical_key": data["to_canonical_key"],
            "scope": data["scope"],
            **({"tenant_id": data["tenant_id"]} if data.get("tenant_id") else {}),
            **({"user_id": data["user_id"]} if data.get("user_id") else {}),
            "schema_version": data["schema_version"],
            "provenance": self._load_json(data["provenance_json"]),
            **(
                {"attributes": self._load_json(data["attributes_json"])}
                if data.get("attributes_json")
                else {}
            ),
        }

    def _validate_fact_record(
        self,
        record: FactRecord,
        *,
        fact_snapshot_id: str,
    ) -> None:
        ensure_non_empty_string(record["id"], label="FactRecord.id")
        ensure_non_empty_string(record["domain"], label="FactRecord.domain")
        ensure_non_empty_string(record["entity_type"], label="FactRecord.entity_type")
        ensure_non_empty_string(record["canonical_key"], label="FactRecord.canonical_key")
        ensure_non_empty_string(record["schema_version"], label="FactRecord.schema_version")
        ensure_scope_shape(
            scope=record.get("scope"),
            tenant_id=record.get("tenant_id"),
            user_id=record.get("user_id"),
            label=f"FactRecord {record['id']}",
        )
        ensure_provenance(record.get("provenance"), label=f"FactRecord {record['id']}.provenance")
        if "layer" in record and record["layer"] != "fact":
            raise ValueError(
                f"FactRecord {record['id']} layer must be 'fact', got {record['layer']!r}."
            )
        if "fact_snapshot_id" in record and record["fact_snapshot_id"] != fact_snapshot_id:
            raise ValueError(
                f"FactRecord {record['id']} fact_snapshot_id does not match the write snapshot."
            )
        if "status" in record:
            ensure_non_empty_string(record["status"], label=f"FactRecord {record['id']}.status")
        if "version" in record:
            version = record["version"]
            if not isinstance(version, int) or version <= 0:
                raise ValueError(f"FactRecord {record['id']}.version must be a positive integer.")
        for field in ("created_at", "updated_at"):
            if field in record:
                ensure_non_empty_string(record[field], label=f"FactRecord {record['id']}.{field}")
        if not isinstance(record.get("attributes"), dict):
            raise ValueError(f"FactRecord {record['id']}.attributes must be a mapping.")

    def _validate_fact_relation(self, relation: FactRelation) -> None:
        ensure_non_empty_string(relation["domain"], label="FactRelation.domain")
        ensure_non_empty_string(relation["relation_type"], label="FactRelation.relation_type")
        ensure_non_empty_string(
            relation["from_canonical_key"],
            label="FactRelation.from_canonical_key",
        )
        ensure_non_empty_string(
            relation["to_canonical_key"],
            label="FactRelation.to_canonical_key",
        )
        ensure_non_empty_string(relation["schema_version"], label="FactRelation.schema_version")
        ensure_scope_shape(
            scope=relation.get("scope"),
            tenant_id=relation.get("tenant_id"),
            user_id=relation.get("user_id"),
            label=f"FactRelation {relation['relation_type']}",
        )
        ensure_provenance(
            relation.get("provenance"),
            label=f"FactRelation {relation['relation_type']}.provenance",
        )
        if "attributes" in relation and not isinstance(relation["attributes"], dict):
            raise ValueError(
                f"FactRelation {relation['relation_type']}.attributes must be a mapping."
            )

    def _load_json(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        return json.loads(value)


class PostgresPersonalAssetRepository(PostgresRepositoryBase):
    def create_record(self, record: PersonalAssetRecord) -> PersonalAssetRecord:
        self._validate_personal_asset_record(record)
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                SELECT asset_id
                FROM personal.asset
                WHERE domain = %s
                  AND tenant_id = %s
                  AND user_id = %s
                  AND identity_key = %s
                LIMIT 1
                """,
                (
                    record["domain"],
                    record["tenant_id"],
                    record["user_id"],
                    record["identity_key"],
                ),
            )
            existing = cursor.fetchone()
            if existing is not None:
                existing_row = self._row_to_dict(existing)
                raise PersonalAssetConflictError(
                    "Personal asset is already registered for this user scope.",
                    details={"asset_id": existing_row["asset_id"]},
                )

            cursor.execute(
                """
                INSERT INTO personal.asset (
                    asset_id,
                    domain,
                    tenant_id,
                    user_id,
                    asset_kind,
                    media_type,
                    filename,
                    blob_sha256,
                    size_bytes,
                    storage_ref,
                    identity_key,
                    status,
                    extraction_status,
                    schema_version
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING
                    asset_id,
                    domain,
                    tenant_id,
                    user_id,
                    asset_kind,
                    media_type,
                    filename,
                    blob_sha256,
                    size_bytes,
                    storage_ref,
                    identity_key,
                    status,
                    extraction_status,
                    schema_version,
                    created_at,
                    updated_at
                """,
                (
                    record["asset_id"],
                    record["domain"],
                    record["tenant_id"],
                    record["user_id"],
                    record["asset_kind"],
                    record["media_type"],
                    record["filename"],
                    record.get("blob_sha256"),
                    record.get("size_bytes"),
                    record["storage_ref"],
                    record["identity_key"],
                    record["status"],
                    record["extraction_status"],
                    record["schema_version"],
                ),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to persist personal asset registration.")
        return self._row_to_personal_asset_record(row)

    def _row_to_personal_asset_record(self, row: Any) -> PersonalAssetRecord:
        data = self._row_to_dict(row)
        return {
            "asset_id": data["asset_id"],
            "domain": data["domain"],
            "tenant_id": data["tenant_id"],
            "user_id": data["user_id"],
            "asset_kind": data["asset_kind"],
            "media_type": data["media_type"],
            "filename": data["filename"],
            "storage_ref": data["storage_ref"],
            "identity_key": data["identity_key"],
            "status": data["status"],
            "extraction_status": data["extraction_status"],
            "schema_version": data["schema_version"],
            **({"blob_sha256": data["blob_sha256"]} if data.get("blob_sha256") else {}),
            **({"size_bytes": int(data["size_bytes"])} if data.get("size_bytes") is not None else {}),
            **({"created_at": str(data["created_at"])} if data.get("created_at") else {}),
            **({"updated_at": str(data["updated_at"])} if data.get("updated_at") else {}),
        }

    def _validate_personal_asset_record(self, record: PersonalAssetRecord) -> None:
        for field in (
            "asset_id",
            "domain",
            "tenant_id",
            "user_id",
            "asset_kind",
            "media_type",
            "filename",
            "storage_ref",
            "identity_key",
            "status",
            "extraction_status",
            "schema_version",
        ):
            ensure_non_empty_string(record.get(field), label=f"PersonalAssetRecord.{field}")
        if "blob_sha256" in record:
            ensure_non_empty_string(record.get("blob_sha256"), label="PersonalAssetRecord.blob_sha256")
        if "size_bytes" in record:
            size_bytes = record["size_bytes"]
            if not isinstance(size_bytes, int) or size_bytes < 0:
                raise ValueError("PersonalAssetRecord.size_bytes must be a non-negative integer.")


class PostgresInterpretationRepository(PostgresRepositoryBase):
    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: ScopeRef,
    ) -> list[InterpretationRecord]:
        if not ids:
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        rows = self._fetch_interpretation_rows(
            where_sql=f"id = ANY(%s) AND {scope_sql}",
            params=[ids, *scope_params],
        )
        by_id = {record["id"]: record for record in rows}
        return [by_id[record_id] for record_id in ids if record_id in by_id]

    def list_records(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        family: str | None = None,
        kind: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 20,
    ) -> list[InterpretationRecord]:
        if limit <= 0:
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref, table_alias="r")
        where_clauses = [f"r.domain = %s", scope_sql]
        params: list[Any] = [domain, *scope_params]

        if family is not None:
            where_clauses.append("r.family = %s")
            params.append(family)
        if kind is not None:
            where_clauses.append("r.kind = %s")
            params.append(kind)
        if subject_type is not None:
            where_clauses.append("r.subject_type = %s")
            params.append(subject_type)
        if subject_id is not None:
            where_clauses.append("r.subject_id = %s")
            params.append(subject_id)
        if statuses:
            where_clauses.append("r.status = ANY(%s)")
            params.append(statuses)

        params.append(limit)

        return self._fetch_interpretation_rows(
            where_sql=" AND ".join(where_clauses),
            params=params,
            order_by="r.updated_at DESC, r.id ASC",
            limit=limit,
        )

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[InterpretationRecord]:
        if limit <= 0 or (not query_text and not query_tokens):
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref, table_alias="r")
        search_expr = _normalized_text_sql(
            "r.id",
            "r.family",
            "r.kind",
            "r.subject_type",
            "r.subject_id",
            "COALESCE(p.title, r.title)",
            "COALESCE(p.claim, r.claim)",
            "COALESCE(p.summary, r.summary)",
            "COALESCE(p.payload_json->>'thesis', r.body_json->>'thesis')",
            "COALESCE(p.payload_json->>'headline', r.body_json->>'headline')",
        )
        vector_sql = _fts_vector_sql(search_expr=search_expr)
        query_sql, query_params = _fts_query_sql(
            query_text=query_text,
            query_tokens=query_tokens,
        )
        return self._fetch_interpretation_rows(
            where_sql=(
                "r.domain = %s "
                f"AND {scope_sql} "
                "AND r.status IN ('published', 'stale') "
                f"AND {vector_sql} @@ {query_sql}"
            ),
            params=[domain, *scope_params, *query_params, *query_params],
            order_by=f"ts_rank_cd({vector_sql}, {query_sql}) DESC, r.updated_at DESC, r.id ASC",
            limit=limit,
        )

    def save_records(
        self,
        records: list[InterpretationRecord],
        snapshot_ref: SnapshotRef,
    ) -> list[str]:
        validated_snapshot_ref = ensure_snapshot_ref(
            snapshot_ref,
            label="InterpretationRepository.snapshot_ref",
        )
        stored_ids: list[str] = []
        with managed_cursor(self.connection) as cursor:
            for record in records:
                self._save_interpretation_record_with_cursor(
                    cursor=cursor,
                    record=record,
                    snapshot_ref=validated_snapshot_ref,
                )
                stored_ids.append(record["id"])
        return stored_ids

    def _fetch_interpretation_rows(
        self,
        *,
        where_sql: str,
        params: list[Any],
        order_by: str = "r.updated_at DESC, r.id ASC",
        limit: int | None = None,
    ) -> list[InterpretationRecord]:
        limit_sql = ""
        final_params = list(params)
        if limit is not None:
            limit_sql = " LIMIT %s"
            final_params.append(limit)

        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    r.id,
                    r.domain,
                    r.family,
                    r.kind,
                    r.subject_type,
                    r.subject_id,
                    r.subject_json,
                    r.scope,
                    r.tenant_id,
                    r.user_id,
                    r.schema_version,
                    r.status,
                    r.confidence,
                    r.fact_snapshot_id,
                    r.interpretation_snapshot_id,
                    r.computed_at,
                    r.expires_at,
                    r.title AS legacy_title,
                    r.claim AS legacy_claim,
                    r.summary AS legacy_summary,
                    p.title AS payload_title,
                    p.claim AS payload_claim,
                    p.summary AS payload_summary,
                    p.payload_json,
                    r.body_json,
                    r.evidence_json,
                    r.relations_json,
                    r.provenance_json,
                    r.render_hints_json
                FROM interp.record AS r
                LEFT JOIN interp.payload AS p
                    ON p.record_id = r.id
                WHERE {where_sql}
                ORDER BY {order_by}{limit_sql}
                """,
                final_params,
            )
            raw_rows = cursor.fetchall()

        if not raw_rows:
            return []

        record_ids = [str(self._row_to_dict(row)["id"]) for row in raw_rows]
        support_links_by_id = self._load_support_links(record_ids)
        return [
            self._row_to_interpretation_record(
                row,
                support_links=support_links_by_id.get(str(self._row_to_dict(row)["id"]), []),
            )
            for row in raw_rows
        ]

    def _load_support_links(
        self,
        record_ids: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        if not record_ids:
            return {}

        grouped: dict[str, list[dict[str, Any]]] = {record_id: [] for record_id in record_ids}
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                SELECT
                    record_id,
                    link_kind,
                    target_layer,
                    target_id,
                    role,
                    weight,
                    support_ref_json,
                    attributes_json
                FROM interp.support_link
                WHERE record_id = ANY(%s)
                ORDER BY record_id ASC, id ASC
                """,
                [record_ids],
            )
            for row in cursor.fetchall():
                data = self._row_to_dict(row)
                if "record_id" not in data:
                    continue
                grouped.setdefault(str(data["record_id"]), []).append(
                    {
                        "link_kind": data["link_kind"],
                        "target_layer": data["target_layer"],
                        **({"target_id": data["target_id"]} if data.get("target_id") else {}),
                        **({"role": data["role"]} if data.get("role") else {}),
                        **(
                            {"weight": float(data["weight"])}
                            if data.get("weight") is not None
                            else {}
                        ),
                        "support_ref": self._load_json(data["support_ref_json"]),
                        "attributes": self._load_json(data["attributes_json"]),
                    }
                )
        return grouped

    def _row_to_interpretation_record(
        self,
        row: Any,
        *,
        support_links: list[dict[str, Any]],
    ) -> InterpretationRecord:
        data = self._row_to_dict(row)
        payload = self._load_json(data.get("payload_json"))
        title = data.get("payload_title") or data.get("legacy_title")
        claim = data.get("payload_claim") or data.get("legacy_claim")
        summary = data.get("payload_summary") or data.get("legacy_summary")
        if title:
            payload["title"] = title
        if claim:
            payload["claim"] = claim
        if summary:
            payload["summary"] = summary

        subject_payload = self._load_json(data.get("subject_json"))
        record = {
            "id": data["id"],
            "domain": data["domain"],
            **({"family": data["family"]} if data.get("family") else {}),
            "kind": data["kind"],
            "subject_type": data["subject_type"],
            "subject_id": data["subject_id"],
            **({"subject": subject_payload} if subject_payload else {}),
            "scope_ref": {
                "scope": data["scope"],
                **({"tenant_id": data["tenant_id"]} if data.get("tenant_id") else {}),
                **({"user_id": data["user_id"]} if data.get("user_id") else {}),
            },
            "schema_version": data["schema_version"],
            "status": data["status"],
            "confidence": data["confidence"],
            "fact_snapshot_id": data["fact_snapshot_id"],
            **(
                {"interpretation_snapshot_id": data["interpretation_snapshot_id"]}
                if data.get("interpretation_snapshot_id")
                else {}
            ),
            "computed_at": str(data["computed_at"]),
            "expires_at": str(data["expires_at"]) if data.get("expires_at") else None,
            "payload": payload,
            "body": self._load_json(data["body_json"]),
            **(
                {"evidence": self._load_json_list(data["evidence_json"])}
                if data.get("evidence_json") is not None
                else {}
            ),
            **(
                {"relations": self._load_json_list(data["relations_json"])}
                if data.get("relations_json") is not None
                else {}
            ),
            "support_links": support_links,
            "provenance": self._load_json(data["provenance_json"]),
            "render_hints": self._load_json(data["render_hints_json"]),
        }
        return materialize_interpretation_record(record)

    def _save_interpretation_record_with_cursor(
        self,
        *,
        cursor: Any,
        record: InterpretationRecord,
        snapshot_ref: SnapshotRef,
    ) -> None:
        materialized = materialize_interpretation_record(record)
        self._validate_interpretation_record(materialized, snapshot_ref=snapshot_ref)
        scope_ref = materialized["scope_ref"]
        payload = interpretation_payload(materialized)
        support_links = interpretation_support_links(materialized)
        payload_json = {
            key: value
            for key, value in payload.items()
            if key not in {"title", "claim", "summary"}
        }
        subject_json = self._subject_json(materialized)

        cursor.execute(
            """
            INSERT INTO interp.record (
                id,
                domain,
                family,
                kind,
                subject_type,
                subject_id,
                subject_json,
                scope,
                tenant_id,
                user_id,
                schema_version,
                status,
                confidence,
                computed_at,
                expires_at,
                title,
                claim,
                summary,
                body_json,
                evidence_json,
                relations_json,
                provenance_json,
                render_hints_json,
                fact_snapshot_id,
                interpretation_snapshot_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                %s::jsonb, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                family = EXCLUDED.family,
                kind = EXCLUDED.kind,
                subject_type = EXCLUDED.subject_type,
                subject_id = EXCLUDED.subject_id,
                subject_json = EXCLUDED.subject_json,
                scope = EXCLUDED.scope,
                tenant_id = EXCLUDED.tenant_id,
                user_id = EXCLUDED.user_id,
                schema_version = EXCLUDED.schema_version,
                status = EXCLUDED.status,
                confidence = EXCLUDED.confidence,
                computed_at = EXCLUDED.computed_at,
                expires_at = EXCLUDED.expires_at,
                title = EXCLUDED.title,
                claim = EXCLUDED.claim,
                summary = EXCLUDED.summary,
                body_json = EXCLUDED.body_json,
                evidence_json = EXCLUDED.evidence_json,
                relations_json = EXCLUDED.relations_json,
                provenance_json = EXCLUDED.provenance_json,
                render_hints_json = EXCLUDED.render_hints_json,
                fact_snapshot_id = EXCLUDED.fact_snapshot_id,
                interpretation_snapshot_id = EXCLUDED.interpretation_snapshot_id,
                updated_at = NOW()
            """,
            (
                materialized["id"],
                materialized["domain"],
                materialized["family"],
                materialized["kind"],
                materialized["subject_type"],
                materialized["subject_id"],
                self._json(subject_json),
                scope_ref["scope"],
                scope_ref.get("tenant_id"),
                scope_ref.get("user_id"),
                materialized["schema_version"],
                materialized["status"],
                materialized["confidence"],
                materialized["computed_at"],
                materialized["expires_at"],
                materialized.get("title"),
                materialized.get("claim"),
                materialized.get("summary"),
                self._json(materialized["body"]),
                self._json(materialized.get("evidence", [])),
                self._json(materialized.get("relations", [])),
                self._json(materialized["provenance"]),
                self._json(materialized["render_hints"]),
                snapshot_ref["fact_snapshot_id"],
                materialized.get("interpretation_snapshot_id"),
            ),
        )
        cursor.execute(
            """
            INSERT INTO interp.payload (
                record_id,
                title,
                claim,
                summary,
                payload_json
            ) VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (record_id) DO UPDATE SET
                title = EXCLUDED.title,
                claim = EXCLUDED.claim,
                summary = EXCLUDED.summary,
                payload_json = EXCLUDED.payload_json,
                updated_at = NOW()
            """,
            (
                materialized["id"],
                materialized.get("title"),
                materialized.get("claim"),
                materialized.get("summary"),
                self._json(payload_json),
            ),
        )
        cursor.execute(
            "DELETE FROM interp.support_link WHERE record_id = %s",
            (materialized["id"],),
        )
        for item in support_links:
            cursor.execute(
                """
                INSERT INTO interp.support_link (
                    record_id,
                    domain,
                    scope,
                    tenant_id,
                    user_id,
                    link_kind,
                    target_layer,
                    target_id,
                    role,
                    weight,
                    support_ref_json,
                    attributes_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
                )
                """,
                (
                    materialized["id"],
                    materialized["domain"],
                    scope_ref["scope"],
                    scope_ref.get("tenant_id"),
                    scope_ref.get("user_id"),
                    item["link_kind"],
                    item["target_layer"],
                    item.get("target_id"),
                    item.get("role"),
                    item.get("weight"),
                    self._json(item.get("support_ref", {})),
                    self._json(item.get("attributes", {})),
                ),
            )

    def _validate_interpretation_record(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> None:
        materialized = materialize_interpretation_record(record)
        ensure_non_empty_string(materialized.get("id"), label="InterpretationRecord.id")
        ensure_non_empty_string(materialized.get("domain"), label="InterpretationRecord.domain")
        ensure_non_empty_string(materialized.get("family"), label="InterpretationRecord.family")
        ensure_non_empty_string(materialized.get("kind"), label="InterpretationRecord.kind")
        ensure_non_empty_string(
            materialized.get("subject_type"),
            label="InterpretationRecord.subject_type",
        )
        ensure_non_empty_string(materialized.get("subject_id"), label="InterpretationRecord.subject_id")
        ensure_non_empty_string(
            materialized.get("schema_version"),
            label="InterpretationRecord.schema_version",
        )
        ensure_scope_ref(
            materialized.get("scope_ref"),
            label=f"InterpretationRecord {materialized['id']}.scope_ref",
        )
        ensure_interpretation_status(
            materialized.get("status"),
            label=f"InterpretationRecord {materialized['id']}.status",
        )
        ensure_non_empty_string(
            materialized["computed_at"],
            label=f"InterpretationRecord {materialized['id']}.computed_at",
        )
        if materialized["expires_at"] is not None:
            ensure_non_empty_string(
                materialized["expires_at"],
                label=f"InterpretationRecord {materialized['id']}.expires_at",
            )
        ensure_provenance(
            materialized.get("provenance"),
            label=f"InterpretationRecord {materialized['id']}.provenance",
        )
        if "layer" in materialized and materialized["layer"] != "interpretation":
            raise ValueError(
                "InterpretationRecord "
                f"{materialized['id']} layer must be 'interpretation', "
                f"got {materialized['layer']!r}."
            )
        if materialized["fact_snapshot_id"] != snapshot_ref["fact_snapshot_id"]:
            raise ValueError(
                "InterpretationRecord "
                f"{materialized['id']} fact_snapshot_id does not match the save snapshot."
            )
        if materialized.get("interpretation_snapshot_id") is not None:
            ensure_non_empty_string(
                materialized["interpretation_snapshot_id"],
                label=(
                    f"InterpretationRecord {materialized['id']}.interpretation_snapshot_id"
                ),
            )
        if not isinstance(materialized.get("payload"), dict):
            raise ValueError(
                f"InterpretationRecord {materialized['id']}.payload must be a mapping."
            )
        if not isinstance(materialized.get("body"), dict):
            raise ValueError(
                f"InterpretationRecord {materialized['id']}.body must be a mapping."
            )
        if not isinstance(materialized.get("render_hints"), dict):
            raise ValueError(
                f"InterpretationRecord {materialized['id']}.render_hints must be a mapping."
            )
        if "support_links" in materialized and not isinstance(materialized["support_links"], list):
            raise ValueError(
                f"InterpretationRecord {materialized['id']}.support_links must be a list when present."
            )
        if "evidence" in materialized and not isinstance(materialized["evidence"], list):
            raise ValueError(
                f"InterpretationRecord {materialized['id']}.evidence must be a list when present."
            )
        if "relations" in materialized and not isinstance(materialized["relations"], list):
            raise ValueError(
                f"InterpretationRecord {materialized['id']}.relations must be a list when present."
            )

    def _load_json(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        return json.loads(value)

    def _load_json_list(self, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if value is None:
            return []
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []

    def _subject_json(self, record: InterpretationRecord) -> dict[str, Any]:
        subject = record.get("subject")
        if isinstance(subject, dict) and subject:
            return dict(subject)
        subject_json = {
            "type": record["subject_type"],
            "id": record["subject_id"],
        }
        label = record.get("subject_label")
        if isinstance(label, str) and label.strip():
            subject_json["label"] = label.strip()
        return subject_json


class PostgresInterpretationPublicationRepository(PostgresInterpretationRepository):
    def publish_bundle(
        self,
        *,
        records: list[InterpretationRecord],
        domain: str,
        snapshot_ref: SnapshotRef,
        outbox_events: list[OutboxEvent],
    ) -> dict[str, Any]:
        validated_snapshot_ref = ensure_snapshot_ref(
            snapshot_ref,
            label="InterpretationPublicationRepository.snapshot_ref",
        )
        cursor = self.connection.cursor()
        try:
            record_ids = self._save_records_with_cursor(
                cursor=cursor,
                records=records,
                snapshot_ref=validated_snapshot_ref,
            )
            snapshot_id = self._publish_snapshot_with_cursor(
                cursor=cursor,
                layer="interpretation",
                domain=domain,
                snapshot_ref=validated_snapshot_ref,
            )
            outbox_event_ids = self._append_events_with_cursor(
                cursor=cursor,
                events=outbox_events,
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return {
            "record_ids": record_ids,
            "snapshot_id": snapshot_id,
            "outbox_event_ids": outbox_event_ids,
        }

    def _save_records_with_cursor(
        self,
        *,
        cursor: Any,
        records: list[InterpretationRecord],
        snapshot_ref: SnapshotRef,
    ) -> list[str]:
        stored_ids: list[str] = []
        for record in records:
            self._save_interpretation_record_with_cursor(
                cursor=cursor,
                record=record,
                snapshot_ref=snapshot_ref,
            )
            stored_ids.append(record["id"])
        return stored_ids

    def _publish_snapshot_with_cursor(
        self,
        *,
        cursor: Any,
        layer: str,
        domain: str,
        snapshot_ref: SnapshotRef,
    ) -> str:
        snapshot_id = snapshot_ref.get("interpretation_snapshot_id") or snapshot_ref["fact_snapshot_id"]
        cursor.execute(
            """
            INSERT INTO ops.snapshot_pointer (
                layer,
                domain,
                current_snapshot_id,
                fact_snapshot_id,
                interpretation_snapshot_id,
                profile_version
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (layer, domain) DO UPDATE SET
                current_snapshot_id = EXCLUDED.current_snapshot_id,
                fact_snapshot_id = EXCLUDED.fact_snapshot_id,
                interpretation_snapshot_id = EXCLUDED.interpretation_snapshot_id,
                profile_version = EXCLUDED.profile_version,
                updated_at = NOW()
            """,
            (
                layer,
                domain,
                snapshot_id,
                snapshot_ref["fact_snapshot_id"],
                snapshot_ref.get("interpretation_snapshot_id"),
                snapshot_ref.get("profile_version"),
            ),
        )
        cursor.execute(
            """
            INSERT INTO ops.snapshot_publication (
                snapshot_id,
                layer,
                domain,
                fact_snapshot_id,
                interpretation_snapshot_id,
                profile_version,
                metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (snapshot_id, layer, domain) DO NOTHING
            """,
            (
                snapshot_id,
                layer,
                domain,
                snapshot_ref["fact_snapshot_id"],
                snapshot_ref.get("interpretation_snapshot_id"),
                snapshot_ref.get("profile_version"),
                self._json({}),
            ),
        )
        return str(snapshot_id)

    def _append_events_with_cursor(
        self,
        *,
        cursor: Any,
        events: list[OutboxEvent],
    ) -> list[str]:
        stored_ids: list[str] = []
        for event in events:
            idempotency_key = event.get("idempotency_key")
            if idempotency_key:
                cursor.execute(
                    """
                    INSERT INTO ops.outbox_event (
                        idempotency_key,
                        event_type,
                        aggregate_layer,
                        aggregate_id,
                        payload_json,
                        status,
                        attempt_count,
                        available_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, NOW())
                    ON CONFLICT (idempotency_key) DO UPDATE SET
                        idempotency_key = EXCLUDED.idempotency_key
                    RETURNING id
                    """,
                    (
                        idempotency_key,
                        event["event_type"],
                        event["aggregate_layer"],
                        event["aggregate_id"],
                        self._json(event["payload"]),
                        "pending",
                        0,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO ops.outbox_event (
                        event_type,
                        aggregate_layer,
                        aggregate_id,
                        payload_json,
                        status,
                        attempt_count,
                        available_at
                    ) VALUES (%s, %s, %s, %s::jsonb, %s, %s, NOW())
                    RETURNING id
                    """,
                    (
                        event["event_type"],
                        event["aggregate_layer"],
                        event["aggregate_id"],
                        self._json(event["payload"]),
                        "pending",
                        0,
                    ),
                )
            row = cursor.fetchone()
            stored_ids.append(str(self._row_to_dict(row)["id"]))
        return stored_ids


class PostgresPersonalRepository(PostgresRepositoryBase):
    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: ScopeRef,
    ) -> list[PersonalRecord]:
        if not ids:
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    domain,
                    kind,
                    title,
                    summary,
                    scope,
                    tenant_id,
                    user_id,
                    fact_snapshot_id,
                    interpretation_snapshot_id,
                    profile_version,
                    path,
                    subspace,
                    status,
                    content_hash,
                    schema_version,
                    version,
                    created_at,
                    updated_at,
                    asset_refs_json,
                    anchors_json,
                    provenance_json
                FROM personal.record
                WHERE id = ANY(%s) AND {scope_sql}
                """,
                [ids, *scope_params],
            )
            return [self._row_to_personal_record(row) for row in cursor.fetchall()]

    def list_records(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        kind: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 20,
    ) -> list[PersonalRecord]:
        if limit <= 0:
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        where_clauses = ["domain = %s", scope_sql]
        params: list[Any] = [domain, *scope_params]
        if kind is not None:
            where_clauses.append("kind = %s")
            params.append(kind)
        if statuses:
            where_clauses.append("status = ANY(%s)")
            params.append(statuses)
        params.append(limit)

        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    domain,
                    kind,
                    title,
                    summary,
                    scope,
                    tenant_id,
                    user_id,
                    fact_snapshot_id,
                    interpretation_snapshot_id,
                    profile_version,
                    path,
                    subspace,
                    status,
                    content_hash,
                    schema_version,
                    version,
                    created_at,
                    updated_at,
                    asset_refs_json,
                    anchors_json,
                    provenance_json
                FROM personal.record
                WHERE {" AND ".join(where_clauses)}
                ORDER BY updated_at DESC, id ASC
                LIMIT %s
                """,
                params,
            )
            return [self._row_to_personal_record(row) for row in cursor.fetchall()]

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[PersonalRecord]:
        if limit <= 0 or (not query_text and not query_tokens):
            return []

        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        search_expr = _normalized_text_sql(
            "id",
            "kind",
            "title",
            "summary",
            "path",
        )
        vector_sql = _fts_vector_sql(search_expr=search_expr)
        query_sql, query_params = _fts_query_sql(
            query_text=query_text,
            query_tokens=query_tokens,
        )
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    domain,
                    kind,
                    title,
                    summary,
                    scope,
                    tenant_id,
                    user_id,
                    fact_snapshot_id,
                    interpretation_snapshot_id,
                    profile_version,
                    path,
                    subspace,
                    status,
                    content_hash,
                    schema_version,
                    version,
                    created_at,
                    updated_at,
                    asset_refs_json,
                    anchors_json,
                    provenance_json
                FROM personal.record
                WHERE domain = %s AND {scope_sql} AND {vector_sql} @@ {query_sql}
                  AND status <> 'deleted'
                ORDER BY ts_rank_cd({vector_sql}, {query_sql}) DESC, updated_at DESC, id ASC
                LIMIT %s
                """,
                [domain, *scope_params, *query_params, *query_params, limit],
            )
            return [self._row_to_personal_record(row) for row in cursor.fetchall()]

    def search_by_anchors(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef | None,
        interpretation_ids: list[str],
        fact_ids: list[str],
        limit: int,
    ) -> list[PersonalRecord]:
        if limit <= 0 or (not interpretation_ids and not fact_ids):
            return []

        if scope_ref is None:
            scope_sql = "TRUE"
            scope_params = []
        else:
            scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        anchor_clauses: list[str] = []
        params: list[Any] = [domain, *scope_params]
        if interpretation_ids:
            anchor_clauses.append(
                "(anchor->>'layer' = 'interpretation' AND anchor->>'id' = ANY(%s))"
            )
            params.append(interpretation_ids)
        if fact_ids:
            anchor_clauses.append(
                "(anchor->>'layer' = 'fact' AND anchor->>'id' = ANY(%s))"
            )
            params.append(fact_ids)

        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    domain,
                    kind,
                    title,
                    summary,
                    scope,
                    tenant_id,
                    user_id,
                    fact_snapshot_id,
                    interpretation_snapshot_id,
                    profile_version,
                    path,
                    subspace,
                    status,
                    content_hash,
                    schema_version,
                    version,
                    created_at,
                    updated_at,
                    asset_refs_json,
                    anchors_json,
                    provenance_json
                FROM personal.record
                WHERE domain = %s
                  AND {scope_sql}
                  AND EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(COALESCE(anchors_json, '[]'::jsonb)) AS anchor
                      WHERE {" OR ".join(anchor_clauses)}
                  )
                ORDER BY updated_at DESC, id ASC
                LIMIT %s
                """,
                [*params, limit],
            )
            return [self._row_to_personal_record(row) for row in cursor.fetchall()]

    def save_record(self, record: PersonalRecord) -> str:
        self._validate_personal_record(record)
        scope_ref = record["scope_ref"]
        snapshot_ref = ensure_snapshot_ref(
            record["snapshot_ref"],
            label=f"PersonalRecord {record['id']}.snapshot_ref",
        )
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                INSERT INTO personal.record (
                    id,
                    domain,
                    kind,
                    title,
                    summary,
                    scope,
                    tenant_id,
                    user_id,
                    fact_snapshot_id,
                    interpretation_snapshot_id,
                    profile_version,
                    path,
                    subspace,
                    status,
                    content_hash,
                    schema_version,
                    version,
                    created_at,
                    asset_refs_json,
                    anchors_json,
                    provenance_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb
                )
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    summary = EXCLUDED.summary,
                    scope = EXCLUDED.scope,
                    tenant_id = EXCLUDED.tenant_id,
                    user_id = EXCLUDED.user_id,
                    fact_snapshot_id = EXCLUDED.fact_snapshot_id,
                    interpretation_snapshot_id = EXCLUDED.interpretation_snapshot_id,
                    profile_version = EXCLUDED.profile_version,
                    path = EXCLUDED.path,
                    subspace = EXCLUDED.subspace,
                    status = EXCLUDED.status,
                    content_hash = EXCLUDED.content_hash,
                    schema_version = EXCLUDED.schema_version,
                    version = EXCLUDED.version,
                    created_at = EXCLUDED.created_at,
                    asset_refs_json = EXCLUDED.asset_refs_json,
                    anchors_json = EXCLUDED.anchors_json,
                    provenance_json = EXCLUDED.provenance_json,
                    updated_at = NOW()
                """,
                (
                    record["id"],
                    record["domain"],
                    record["kind"],
                    record["title"],
                    record["summary"],
                    scope_ref["scope"],
                    scope_ref.get("tenant_id"),
                    scope_ref.get("user_id"),
                    snapshot_ref["fact_snapshot_id"],
                    snapshot_ref.get("interpretation_snapshot_id"),
                    record["profile_version"],
                    self._personal_record_path(record),
                    str(record.get("subspace") or "raw"),
                    record["status"],
                    str(record.get("content_hash") or ""),
                    record["schema_version"],
                    int(record.get("version") or 1),
                    str(record.get("created_at") or record.get("updated_at") or datetime.now(UTC).isoformat()),
                    self._json(record.get("asset_refs", [])),
                    self._json(record.get("anchors", [])),
                    self._json(record["provenance"]),
                ),
            )
        return record["id"]

    def _row_to_personal_record(self, row: Any) -> PersonalRecord:
        data = self._row_to_dict(row)
        raw_anchors = data.get("anchors_json")
        if isinstance(raw_anchors, str):
            raw_anchors = json.loads(raw_anchors)
        raw_asset_refs = data.get("asset_refs_json")
        if isinstance(raw_asset_refs, str):
            raw_asset_refs = json.loads(raw_asset_refs)
        provenance = self._load_json(data["provenance_json"])
        path = data.get("path")
        subspace = data.get("subspace") or "raw"
        asset_refs = raw_asset_refs
        if not isinstance(asset_refs, list):
            asset_refs = []
        version = data.get("version") if self._is_positive_int(data.get("version")) else 1
        created_at = data.get("created_at") or data.get("updated_at")
        return {
            "id": data["id"],
            "domain": data["domain"],
            "kind": data["kind"],
            "title": data["title"],
            "summary": data["summary"],
            "scope_ref": {
                "scope": data["scope"],
                **({"tenant_id": data["tenant_id"]} if data.get("tenant_id") else {}),
                **({"user_id": data["user_id"]} if data.get("user_id") else {}),
            },
            "snapshot_ref": {
                "fact_snapshot_id": data["fact_snapshot_id"],
                **(
                    {"interpretation_snapshot_id": data["interpretation_snapshot_id"]}
                    if data.get("interpretation_snapshot_id")
                    else {}
                ),
                **({"profile_version": data["profile_version"]} if data.get("profile_version") else {}),
            },
            "profile_version": data["profile_version"],
            "path": path,
            "subspace": subspace,
            "asset_refs": [
                str(value)
                for value in asset_refs
                if isinstance(value, str) and value.strip()
            ],
            "content_hash": str(data.get("content_hash") or ""),
            **(
                {"anchors": ensure_personal_anchors(raw_anchors, label=f"PersonalRecord {data['id']}.anchors")}
                if raw_anchors is not None
                else {}
            ),
            "status": data["status"],
            "schema_version": data["schema_version"],
            "version": int(version),
            "created_at": str(created_at),
            **({"updated_at": str(data["updated_at"])} if data.get("updated_at") else {}),
            "provenance": provenance,
        }

    def _validate_personal_record(self, record: PersonalRecord) -> None:
        ensure_non_empty_string(record["id"], label="PersonalRecord.id")
        ensure_non_empty_string(record["domain"], label="PersonalRecord.domain")
        ensure_non_empty_string(record["kind"], label="PersonalRecord.kind")
        ensure_non_empty_string(record["title"], label="PersonalRecord.title")
        ensure_non_empty_string(record["summary"], label="PersonalRecord.summary")
        ensure_non_empty_string(
            record["profile_version"],
            label="PersonalRecord.profile_version",
        )
        ensure_non_empty_string(self._personal_record_path(record), label="PersonalRecord.path")
        ensure_non_empty_string(record["status"], label="PersonalRecord.status")
        ensure_non_empty_string(
            record["schema_version"],
            label="PersonalRecord.schema_version",
        )
        if "anchors" in record:
            ensure_personal_anchors(
                record.get("anchors"),
                label=f"PersonalRecord {record['id']}.anchors",
            )
        scope_ref = ensure_scope_ref(
            record.get("scope_ref"),
            label=f"PersonalRecord {record['id']}.scope_ref",
        )
        if scope_ref["scope"] != "user":
            raise ValueError(f"PersonalRecord {record['id']} must use user scope.")
        snapshot_ref = ensure_snapshot_ref(
            record.get("snapshot_ref"),
            label=f"PersonalRecord {record['id']}.snapshot_ref",
        )
        if snapshot_ref.get("profile_version") and snapshot_ref["profile_version"] != record["profile_version"]:
            raise ValueError(
                f"PersonalRecord {record['id']} snapshot_ref.profile_version must match profile_version."
            )
        ensure_provenance(
            record.get("provenance"),
            label=f"PersonalRecord {record['id']}.provenance",
        )
        if "layer" in record and record["layer"] != "personal":
            raise ValueError(
                f"PersonalRecord {record['id']} layer must be 'personal', got {record['layer']!r}."
            )
        if "subspace" in record and str(record["subspace"]) not in {"raw", "wiki"}:
            raise ValueError(
                f"PersonalRecord {record['id']} subspace must be 'raw' or 'wiki'."
            )
        if "asset_refs" in record:
            asset_refs = record.get("asset_refs")
            if not isinstance(asset_refs, list) or any(
                not isinstance(item, str) or not item.strip()
                for item in asset_refs
            ):
                raise ValueError(
                    f"PersonalRecord {record['id']} asset_refs must be a list of non-empty strings."
                )

    def _personal_record_path(self, record: PersonalRecord) -> str:
        path = record.get("path")
        if not isinstance(path, str):
            raise ValueError(f"PersonalRecord {record['id']} path must be a string.")
        return path

    def _load_json(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        return json.loads(value)

    def _is_positive_int(self, value: Any) -> bool:
        return isinstance(value, int) and value > 0


class PostgresProfileContextRepository(PostgresRepositoryBase):
    def get_profile_context(
        self,
        domain: str,
        tenant_id: str,
        user_id: str,
    ) -> ProfileContext:
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                SELECT
                    user_id,
                    tenant_id,
                    domain,
                    profile_version,
                    goals_json,
                    preferences_json,
                    attributes_json
                FROM personal.profile_context
                WHERE domain = %s AND tenant_id = %s AND user_id = %s
                """,
                (domain, tenant_id, user_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(
                    f"No profile context found for domain={domain!r}, tenant_id={tenant_id!r}, user_id={user_id!r}"
                )
            data = self._row_to_dict(row)
            return {
                "user_id": data["user_id"],
                "tenant_id": data["tenant_id"],
                "domain": data["domain"],
                "profile_version": data["profile_version"],
                "goals": self._load_list(data["goals_json"]),
                "preferences": self._load_dict(data["preferences_json"]),
                "attributes": self._load_dict(data["attributes_json"]),
            }

    def save_profile_context(self, profile: ProfileContext) -> None:
        self._validate_profile_context(profile)
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                INSERT INTO personal.profile_context (
                    domain,
                    tenant_id,
                    user_id,
                    profile_version,
                    goals_json,
                    preferences_json,
                    attributes_json
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                ON CONFLICT (domain, tenant_id, user_id) DO UPDATE SET
                    profile_version = EXCLUDED.profile_version,
                    goals_json = EXCLUDED.goals_json,
                    preferences_json = EXCLUDED.preferences_json,
                    attributes_json = EXCLUDED.attributes_json,
                    updated_at = NOW()
                """,
                (
                    profile["domain"],
                    profile["tenant_id"],
                    profile["user_id"],
                    profile["profile_version"],
                    self._json(profile.get("goals", [])),
                    self._json(profile.get("preferences", {})),
                    self._json(profile.get("attributes", {})),
                ),
            )

    def _load_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if value is None:
            return []
        return json.loads(value)

    def _load_dict(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        return json.loads(value)

    def _validate_profile_context(self, profile: ProfileContext) -> None:
        ensure_non_empty_string(
            profile.get("domain"),
            label="ProfileContext.domain",
        )
        ensure_non_empty_string(
            profile.get("tenant_id"),
            label="ProfileContext.tenant_id",
        )
        ensure_non_empty_string(
            profile.get("user_id"),
            label="ProfileContext.user_id",
        )
        ensure_non_empty_string(
            profile.get("profile_version"),
            label="ProfileContext.profile_version",
        )
        if not isinstance(profile.get("goals"), list):
            raise ValueError("ProfileContext.goals must be a list.")
        if not isinstance(profile.get("preferences"), dict):
            raise ValueError("ProfileContext.preferences must be a mapping.")
        if not isinstance(profile.get("attributes"), dict):
            raise ValueError("ProfileContext.attributes must be a mapping.")


class PostgresSnapshotRepository(PostgresRepositoryBase):
    def publish_snapshot(
        self,
        layer: str,
        domain: str,
        snapshot_ref: SnapshotRef,
    ) -> str:
        ensure_non_empty_string(layer, label="SnapshotRepository.layer")
        ensure_non_empty_string(domain, label="SnapshotRepository.domain")
        validated_snapshot_ref = ensure_snapshot_ref(
            snapshot_ref,
            label="SnapshotRepository.snapshot_ref",
        )
        snapshot_id = (
            validated_snapshot_ref.get("interpretation_snapshot_id")
            or validated_snapshot_ref["fact_snapshot_id"]
        )
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                INSERT INTO ops.snapshot_pointer (
                    layer,
                    domain,
                    current_snapshot_id,
                    fact_snapshot_id,
                    interpretation_snapshot_id,
                    profile_version
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (layer, domain) DO UPDATE SET
                    current_snapshot_id = EXCLUDED.current_snapshot_id,
                    fact_snapshot_id = EXCLUDED.fact_snapshot_id,
                    interpretation_snapshot_id = EXCLUDED.interpretation_snapshot_id,
                    profile_version = EXCLUDED.profile_version,
                    updated_at = NOW()
                """,
                (
                    layer,
                    domain,
                    snapshot_id,
                    validated_snapshot_ref["fact_snapshot_id"],
                    validated_snapshot_ref.get("interpretation_snapshot_id"),
                    validated_snapshot_ref.get("profile_version"),
                ),
            )
            cursor.execute(
                """
                INSERT INTO ops.snapshot_publication (
                    snapshot_id,
                    layer,
                    domain,
                    fact_snapshot_id,
                    interpretation_snapshot_id,
                    profile_version,
                    metadata_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (snapshot_id, layer, domain) DO NOTHING
                """,
                (
                    snapshot_id,
                    layer,
                    domain,
                    validated_snapshot_ref["fact_snapshot_id"],
                    validated_snapshot_ref.get("interpretation_snapshot_id"),
                    validated_snapshot_ref.get("profile_version"),
                    self._json({}),
                ),
            )
        return snapshot_id

    def get_snapshot_status(
        self,
        *,
        layer: str | None = None,
        domain: str,
    ) -> dict[str, object] | None:
        where_clause = "p.domain = %s"
        params: list[Any] = [domain]
        if layer is not None:
            where_clause += " AND p.layer = %s"
            params.append(layer)

        with managed_cursor(self.connection) as cursor:
            query = f"""
                SELECT
                    p.layer,
                    p.domain,
                    p.current_snapshot_id,
                    p.fact_snapshot_id,
                    p.interpretation_snapshot_id,
                    p.profile_version,
                    p.updated_at,
                    pub.published_at
                FROM ops.snapshot_pointer p
                LEFT JOIN ops.snapshot_publication pub
                    ON pub.snapshot_id = p.current_snapshot_id
                    AND pub.layer = p.layer
                    AND pub.domain = p.domain
                WHERE {where_clause}
                ORDER BY p.updated_at DESC, p.layer ASC
            """
            cursor.execute(
                query if layer is None else query + "\nLIMIT 1",
                params,
            )
            if layer is not None:
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._snapshot_status_from_row(row)

            rows = cursor.fetchall()
            if not rows:
                return None
            layers: dict[str, dict[str, object]] = {}
            for row in rows:
                status = self._snapshot_status_from_row(row)
                layers[str(status["layer"])] = status
            return {
                "domain": domain,
                "layers": layers,
            }

    def _snapshot_status_from_row(self, row: Mapping[str, Any] | Any) -> dict[str, object]:
        data = self._row_to_dict(row)
        return {
            "layer": data["layer"],
            "domain": data["domain"],
            "current_snapshot_id": data["current_snapshot_id"],
            "fact_snapshot_id": data["fact_snapshot_id"],
            **(
                {"interpretation_snapshot_id": data["interpretation_snapshot_id"]}
                if data.get("interpretation_snapshot_id")
                else {}
            ),
            **({"profile_version": data["profile_version"]} if data.get("profile_version") else {}),
            **({"updated_at": str(data["updated_at"])} if data.get("updated_at") else {}),
            **({"published_at": str(data["published_at"])} if data.get("published_at") else {}),
        }


class PostgresOutboxRepository(PostgresRepositoryBase):
    def get_event(self, event_id: str) -> OutboxEventRecord:
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    idempotency_key,
                    event_type,
                    aggregate_layer,
                    aggregate_id,
                    payload_json,
                    status,
                    attempt_count,
                    available_at,
                    claimed_at,
                    processed_at,
                    last_error
                FROM ops.outbox_event
                WHERE id = %s
                """,
                (event_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise KeyError(f"Unknown outbox event: {event_id}")
        return self._row_to_outbox_event_record(row)

    def has_pending_events_for_aggregate(
        self,
        *,
        aggregate_layer: str,
        aggregate_id: str,
    ) -> bool:
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM ops.outbox_event
                    WHERE aggregate_layer = %s
                        AND aggregate_id = %s
                        AND status IN ('pending', 'claimed')
                ) AS has_pending
                """,
                (aggregate_layer, aggregate_id),
            )
            row = cursor.fetchone()
        if row is None:
            return False
        return bool(self._row_to_dict(row).get("has_pending"))

    def append_events(self, events: list[OutboxEvent]) -> list[str]:
        stored_ids: list[str] = []
        with managed_cursor(self.connection) as cursor:
            for event in events:
                idempotency_key = event.get("idempotency_key")
                if idempotency_key:
                    cursor.execute(
                        """
                        INSERT INTO ops.outbox_event (
                            idempotency_key,
                            event_type,
                            aggregate_layer,
                            aggregate_id,
                            payload_json,
                            status,
                            attempt_count,
                            available_at
                        ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, NOW())
                        ON CONFLICT (idempotency_key) DO UPDATE SET
                            idempotency_key = EXCLUDED.idempotency_key
                        RETURNING id
                        """,
                        (
                            idempotency_key,
                            event["event_type"],
                            event["aggregate_layer"],
                            event["aggregate_id"],
                            self._json(event["payload"]),
                            "pending",
                            0,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO ops.outbox_event (
                            event_type,
                            aggregate_layer,
                            aggregate_id,
                            payload_json,
                            status,
                            attempt_count,
                            available_at
                        ) VALUES (%s, %s, %s, %s::jsonb, %s, %s, NOW())
                        RETURNING id
                        """,
                        (
                            event["event_type"],
                            event["aggregate_layer"],
                            event["aggregate_id"],
                            self._json(event["payload"]),
                            "pending",
                            0,
                        ),
                    )
                row = cursor.fetchone()
                stored_ids.append(str(self._row_to_dict(row)["id"]))
        return stored_ids

    def claim_pending(
        self,
        *,
        limit: int,
        event_types: list[str] | None = None,
    ) -> list[OutboxEventRecord]:
        filters = ["status = 'pending'", "available_at <= NOW()"]
        params: list[Any] = []

        if event_types:
            filters.append("event_type = ANY(%s)")
            params.append(event_types)

        params.append(limit)
        where_sql = " AND ".join(filters)

        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                WITH candidates AS (
                    SELECT id
                    FROM ops.outbox_event
                    WHERE {where_sql}
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT %s
                )
                UPDATE ops.outbox_event AS e
                SET
                    status = 'claimed',
                    claimed_at = NOW(),
                    attempt_count = e.attempt_count + 1
                FROM candidates
                WHERE e.id = candidates.id
                RETURNING
                    e.id,
                    e.idempotency_key,
                    e.event_type,
                    e.aggregate_layer,
                    e.aggregate_id,
                    e.payload_json,
                    e.status,
                    e.attempt_count,
                    e.available_at,
                    e.claimed_at,
                    e.processed_at,
                    e.last_error
                """
                ,
                params,
            )
            return [self._row_to_outbox_event_record(row) for row in cursor.fetchall()]

    def mark_processed(self, event_id: str) -> None:
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                UPDATE ops.outbox_event
                SET
                    status = 'processed',
                    processed_at = NOW(),
                    last_error = NULL
                WHERE id = %s
                """,
                (event_id,),
            )

    def mark_failed(
        self,
        event_id: str,
        error_message: str,
        *,
        retryable: bool = True,
    ) -> None:
        max_attempts = 3
        base_delay_seconds = 30

        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                """
                UPDATE ops.outbox_event
                SET
                    status = CASE
                        WHEN %s AND attempt_count < %s THEN 'pending'
                        ELSE 'failed'
                    END,
                    available_at = CASE
                        WHEN %s AND attempt_count < %s THEN
                            NOW()
                            + (
                                (%s * POWER(2, GREATEST(attempt_count - 1, 0)))
                                * INTERVAL '1 second'
                            )
                        ELSE available_at
                    END,
                    claimed_at = CASE
                        WHEN %s AND attempt_count < %s THEN NULL
                        ELSE claimed_at
                    END,
                    last_error = %s
                WHERE id = %s
                """,
                (
                    retryable,
                    max_attempts,
                    retryable,
                    max_attempts,
                    base_delay_seconds,
                    retryable,
                    max_attempts,
                    error_message,
                    event_id,
                ),
            )

    def _row_to_outbox_event_record(self, row: Any) -> OutboxEventRecord:
        data = self._row_to_dict(row)
        return {
            "id": str(data["id"]),
            "idempotency_key": data.get("idempotency_key"),
            "event_type": data["event_type"],
            "aggregate_layer": data["aggregate_layer"],
            "aggregate_id": data["aggregate_id"],
            "payload": self._load_json(data["payload_json"]),
            "status": data["status"],
            "attempt_count": data["attempt_count"],
            "available_at": str(data["available_at"]),
            "claimed_at": str(data["claimed_at"]) if data.get("claimed_at") else None,
            "processed_at": str(data["processed_at"]) if data.get("processed_at") else None,
            "last_error": data.get("last_error"),
        }

    def _load_json(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        return json.loads(value)


class PostgresDependencyRepository(PostgresRepositoryBase):
    def replace_edges_for_target(
        self,
        *,
        domain: str,
        to_layer: str,
        to_id: str,
        scope_ref: ScopeRef,
        edges: list[DependencyEdge],
    ) -> None:
        scope_sql, scope_params = self._scope_filter_sql(scope_ref)
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                DELETE FROM graph.dependency_edge
                WHERE domain = %s
                  AND to_layer = %s
                  AND to_id = %s
                  AND {scope_sql}
                """,
                [domain, to_layer, to_id, *scope_params],
            )
            for edge in edges:
                edge_scope_ref = edge["scope_ref"]
                cursor.execute(
                    """
                    INSERT INTO graph.dependency_edge (
                        domain,
                        from_layer,
                        from_id,
                        to_layer,
                        to_id,
                        scope,
                        tenant_id,
                        user_id,
                        edge_type,
                        attributes_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        edge["domain"],
                        edge["from_layer"],
                        edge["from_id"],
                        edge["to_layer"],
                        edge["to_id"],
                        edge_scope_ref["scope"],
                        edge_scope_ref.get("tenant_id"),
                        edge_scope_ref.get("user_id"),
                        edge.get("edge_type"),
                        self._json(edge.get("attributes", {})),
                    ),
                )

    def get_impact(
        self,
        domain: str,
        layer: str,
        record_id: str,
        scope_ref: ScopeRef,
    ) -> DependencyImpact:
        scope_sql, scope_params = self._scope_filter_sql(scope_ref, table_alias="d")
        with managed_cursor(self.connection) as cursor:
            cursor.execute(
                f"""
                SELECT d.to_layer, d.to_id, rp.path AS rendered_path
                FROM graph.dependency_edge d
                LEFT JOIN graph.rendered_page rp
                  ON rp.layer = d.to_layer
                 AND rp.record_id = d.to_id
                 AND rp.scope = d.scope
                 AND COALESCE(rp.tenant_id, '') = COALESCE(d.tenant_id, '')
                 AND COALESCE(rp.user_id, '') = COALESCE(d.user_id, '')
                WHERE d.domain = %s
                  AND d.from_layer = %s
                  AND d.from_id = %s
                  AND {scope_sql}
                """,
                [domain, layer, record_id, *scope_params],
            )
            rows = [self._row_to_dict(row) for row in cursor.fetchall()]

        affected_interpretation_ids = [row["to_id"] for row in rows if row["to_layer"] == "interpretation"]
        affected_personal_ids = [row["to_id"] for row in rows if row["to_layer"] == "personal"]
        affected_rendered_paths = [row["rendered_path"] for row in rows if row.get("rendered_path")]

        return {
            "affected_interpretation_ids": affected_interpretation_ids,
            "affected_rendered_paths": affected_rendered_paths,
            "affected_personal_ids": affected_personal_ids,
        }
