from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from wiki_mcp.schemas.domain_pack_review import DomainPackApprovalAuditRecord


def _matches_text(query_text: str, query_tokens: list[str], *parts: object) -> bool:
    haystack = " ".join(str(part or "") for part in parts).lower()
    if query_text and query_text.lower() in haystack:
        return True
    return any(token in haystack for token in query_tokens)


@dataclass
class InMemoryFactRepository:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    relations: list[dict[str, Any]] = field(default_factory=list)

    def get_by_canonical_keys(self, canonical_keys: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(record) for record in self.records.values() if record["canonical_key"] in canonical_keys]

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(self.records[record_id]) for record_id in ids if record_id in self.records]

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: dict[str, Any],
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        matches = [
            dict(record)
            for record in self.records.values()
            if record["domain"] == domain
            and _matches_text(
                query_text,
                query_tokens,
                record["id"],
                record["entity_type"],
                record["canonical_key"],
                record.get("attributes", {}).get("title"),
                record.get("attributes", {}).get("name"),
                record.get("attributes", {}).get("label"),
                record.get("attributes", {}).get("summary"),
            )
        ]
        return matches[:limit]

    def write_facts(
        self,
        records: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        *,
        fact_snapshot_id: str,
    ) -> dict[str, Any]:
        facts_created = 0
        facts_updated = 0
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        for record in records:
            scope = str(record["scope"])
            existing_by_key = next(
                (
                    existing
                    for existing in self.records.values()
                    if existing["canonical_key"] == record["canonical_key"]
                    and existing["scope"] == scope
                    and existing.get("tenant_id") == record.get("tenant_id")
                    and existing.get("user_id") == record.get("user_id")
                ),
                None,
            )
            if existing_by_key is not None and existing_by_key["id"] != record["id"]:
                raise ValueError(
                    "Canonical Fact identity conflict at storage boundary for "
                    f"{record['canonical_key']!r}: existing id {existing_by_key['id']!r}, "
                    f"incoming id {record['id']!r}."
                )

            existing_by_id = self.records.get(record["id"])
            current = existing_by_id or existing_by_key
            persisted = dict(record)
            persisted["layer"] = "fact"
            persisted["fact_snapshot_id"] = fact_snapshot_id
            persisted["status"] = str(record.get("status") or (current or {}).get("status") or "active")
            persisted["version"] = (
                int(record["version"])
                if "version" in record
                else int((current or {}).get("version") or 0) + 1
            )
            persisted["created_at"] = str(record.get("created_at") or (current or {}).get("created_at") or timestamp)
            persisted["updated_at"] = str(record.get("updated_at") or timestamp)
            self.records[persisted["id"]] = persisted
            if current is None:
                facts_created += 1
            else:
                facts_updated += 1
        self.relations.extend(dict(relation) for relation in relations)
        return {
            "facts_created": facts_created,
            "facts_updated": facts_updated,
            "relations_created": len(relations),
            "affected_fact_ids": [record["id"] for record in records],
        }


@dataclass
class InMemoryInterpretationRepository:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(self.records[record_id]) for record_id in ids if record_id in self.records]

    def list_records(
        self,
        *,
        domain: str,
        scope_ref: dict[str, Any],
        family: str | None = None,
        kind: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for record in self.records.values():
            if record["domain"] != domain:
                continue
            if family is not None and record.get("family") != family:
                continue
            if kind is not None and record.get("kind") != kind:
                continue
            if subject_type is not None and record.get("subject_type") != subject_type:
                continue
            if subject_id is not None and record.get("subject_id") != subject_id:
                continue
            if statuses and record.get("status") not in statuses:
                continue
            matches.append(dict(record))
        return matches[:limit]

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: dict[str, Any],
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        matches = [
            dict(record)
            for record in self.records.values()
            if record["domain"] == domain
            and record.get("status") in {"published", "stale"}
            and _matches_text(
                query_text,
                query_tokens,
                record["id"],
                record.get("family"),
                record.get("kind"),
                record.get("subject_id"),
                record.get("title"),
                record.get("claim"),
                record.get("summary"),
            )
        ]
        return matches[:limit]

    def save_records(self, records: list[dict[str, Any]], snapshot_ref: dict[str, Any]) -> list[str]:
        for record in records:
            persisted = dict(record)
            self.records[persisted["id"]] = persisted
        return [record["id"] for record in records]


@dataclass
class InMemoryPersonalRepository:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(self.records[record_id]) for record_id in ids if record_id in self.records]

    def search_for_retrieval(
        self,
        *,
        domain: str,
        scope_ref: dict[str, Any],
        query_text: str,
        query_tokens: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        matches = [
            dict(record)
            for record in self.records.values()
            if record["domain"] == domain
            and record["scope_ref"].get("tenant_id") == scope_ref.get("tenant_id")
            and record["scope_ref"].get("user_id") == scope_ref.get("user_id")
            and _matches_text(
                query_text,
                query_tokens,
                record["id"],
                record.get("kind"),
                record.get("title"),
                record.get("summary"),
                record.get("body_path"),
            )
        ]
        return matches[:limit]

    def search_by_anchors(
        self,
        *,
        domain: str,
        scope_ref: dict[str, Any],
        interpretation_ids: list[str],
        fact_ids: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0 or (not interpretation_ids and not fact_ids):
            return []

        interpretation_id_set = set(interpretation_ids)
        fact_id_set = set(fact_ids)
        matches = [
            dict(record)
            for record in self.records.values()
            if record["domain"] == domain
            and record["scope_ref"].get("tenant_id") == scope_ref.get("tenant_id")
            and record["scope_ref"].get("user_id") == scope_ref.get("user_id")
            and any(
                isinstance(anchor, dict)
                and (
                    (anchor.get("layer") == "interpretation" and anchor.get("id") in interpretation_id_set)
                    or (anchor.get("layer") == "fact" and anchor.get("id") in fact_id_set)
                )
                for anchor in (record.get("anchors") or [])
            )
        ]
        return matches[:limit]

    def save_record(self, record: dict[str, Any]) -> str:
        self.records[record["id"]] = dict(record)
        return str(record["id"])


@dataclass
class InMemoryProfileContextRepository:
    profiles: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)

    def get_profile_context(self, domain: str, tenant_id: str, user_id: str) -> dict[str, Any]:
        key = (domain, tenant_id, user_id)
        if key not in self.profiles:
            raise KeyError(
                f"No profile context found for domain={domain!r}, tenant_id={tenant_id!r}, user_id={user_id!r}"
            )
        return dict(self.profiles[key])


@dataclass
class InMemorySnapshotRepository:
    status_by_layer: dict[str, dict[str, Any]] = field(default_factory=dict)

    def publish_snapshot(self, layer: str, domain: str, snapshot_ref: dict[str, Any]) -> str:
        snapshot_id = snapshot_ref.get("interpretation_snapshot_id") or snapshot_ref["fact_snapshot_id"]
        self.status_by_layer[layer] = {
            "layer": layer,
            "domain": domain,
            "current_snapshot_id": snapshot_id,
            "fact_snapshot_id": snapshot_ref["fact_snapshot_id"],
            **(
                {"interpretation_snapshot_id": snapshot_ref["interpretation_snapshot_id"]}
                if "interpretation_snapshot_id" in snapshot_ref
                else {}
            ),
            **({"profile_version": snapshot_ref["profile_version"]} if "profile_version" in snapshot_ref else {}),
            "published_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        return str(snapshot_id)

    def get_snapshot_status(self, *, layer: str | None = None, domain: str) -> dict[str, object] | None:
        status = self.status_by_layer.get("fact") if layer is None else self.status_by_layer.get(layer)
        if status is None:
            return None
        return dict(status)


@dataclass
class InMemoryOutboxRepository:
    events: list[dict[str, Any]] = field(default_factory=list)

    def append_events(self, events: list[dict[str, Any]]) -> list[str]:
        start = len(self.events) + 1
        self.events.extend(dict(event) for event in events)
        return [f"evt-{index}" for index in range(start, start + len(events))]


@dataclass
class InMemoryDomainPackReviewAuditRepository:
    records: list[DomainPackApprovalAuditRecord] = field(default_factory=list)

    def append_record(self, record: DomainPackApprovalAuditRecord) -> str:
        stored = dict(record)
        record_id = str(stored.get("record_id") or f"pack_audit:{len(self.records) + 1}")
        stored["record_id"] = record_id
        self.records.append(stored)
        return record_id
