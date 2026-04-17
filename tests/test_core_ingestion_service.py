from __future__ import annotations

from wiki_mcp.services.core_ingestion import DefaultCoreIngestionService


class StubPlugin:
    domain_name = "recruiting"
    schema_version = "v1"

    def accepts(self, source: dict[str, object]) -> bool:
        return source["domain"] == "recruiting"

    def normalize_source(self, source: dict[str, object]) -> dict[str, object]:
        return {
            **source,
            "metadata": {
                **source["metadata"],
                "normalized": True,
            },
        }

    def extract_fact_records(self, source: dict[str, object]) -> list[dict[str, object]]:
        return [
            {
                "id": "fact:job_posting:emp-1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job_posting:emp-1",
                "attributes": {"title": "Backend Engineer"},
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": source["source_id"]},
            },
            {
                "id": "fact:company:comp-1",
                "domain": "recruiting",
                "entity_type": "company",
                "canonical_key": "company:comp-1",
                "attributes": {"name": "JobsWiki"},
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": source["source_id"]},
            },
        ]

    def extract_fact_relations(
        self,
        source: dict[str, object],
        records: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        return [
            {
                "domain": "recruiting",
                "relation_type": "posted_by",
                "from_canonical_key": records[0]["canonical_key"],
                "to_canonical_key": records[1]["canonical_key"],
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": source["source_id"]},
            }
        ]

    def validate_batch(
        self,
        source: dict[str, object],
        records: list[dict[str, object]],
        relations: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "ok": True,
            "warnings": [],
            "errors": [],
        }


class StubFactRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict[str, object]], list[dict[str, object]], str]] = []

    def write_facts(
        self,
        records: list[dict[str, object]],
        relations: list[dict[str, object]],
        *,
        fact_snapshot_id: str,
    ) -> dict[str, object]:
        self.calls.append((records, relations, fact_snapshot_id))
        return {
            "facts_created": len(records),
            "facts_updated": 0,
            "relations_created": len(relations),
            "affected_fact_ids": [record["id"] for record in records],
        }


class StubSnapshotRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def publish_snapshot(
        self,
        layer: str,
        domain: str,
        snapshot_ref: dict[str, str],
    ) -> str:
        self.calls.append((layer, domain, snapshot_ref))
        return snapshot_ref["fact_snapshot_id"]


class StubOutboxRepository:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, object]]] = []

    def append_events(self, events: list[dict[str, object]]) -> list[str]:
        self.calls.append(events)
        return [f"evt-{index}" for index, _ in enumerate(events, start=1)]


def _source() -> dict[str, object]:
    return {
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


def test_prepare_batch_normalizes_and_validates() -> None:
    service = DefaultCoreIngestionService(
        fact_repository=StubFactRepository(),
        snapshot_repository=StubSnapshotRepository(),
        outbox_repository=StubOutboxRepository(),
    )

    batch = service.prepare_batch(_source(), StubPlugin())

    assert batch["source"]["metadata"]["normalized"] is True
    assert batch["validation"]["ok"] is True
    assert batch["records"][0]["canonical_key"] == "job_posting:emp-1"
    assert batch["relations"][0]["relation_type"] == "posted_by"


def test_prepare_batch_rejects_invalid_relation_targets() -> None:
    class BrokenRelationPlugin(StubPlugin):
        def extract_fact_relations(
            self,
            source: dict[str, object],
            records: list[dict[str, object]],
        ) -> list[dict[str, object]]:
            return [
                {
                    "domain": "recruiting",
                    "relation_type": "posted_by",
                    "from_canonical_key": "job_posting:missing",
                    "to_canonical_key": "company:missing",
                    "scope": "shared",
                    "schema_version": "v1",
                    "provenance": {"source_id": source["source_id"]},
                }
            ]

    service = DefaultCoreIngestionService(
        fact_repository=StubFactRepository(),
        snapshot_repository=StubSnapshotRepository(),
        outbox_repository=StubOutboxRepository(),
    )

    batch = service.prepare_batch(_source(), BrokenRelationPlugin())

    assert batch["validation"]["ok"] is False
    assert "missing from_canonical_key" in batch["validation"]["errors"][0]


def test_ingest_source_wires_fact_write_snapshot_and_outbox() -> None:
    fact_repository = StubFactRepository()
    snapshot_repository = StubSnapshotRepository()
    outbox_repository = StubOutboxRepository()
    service = DefaultCoreIngestionService(
        fact_repository=fact_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
    )

    result = service.ingest_source(_source(), StubPlugin())

    assert result["facts_created"] == 2
    assert result["relations_created"] == 1
    assert result["affected_fact_ids"] == [
        "fact:job_posting:emp-1",
        "fact:company:comp-1",
    ]
    assert result["outbox_event_ids"] == ["evt-1"]
    assert result["fact_snapshot_id"].startswith("fact_snap:recruiting:EMP-1:")

    assert len(fact_repository.calls) == 1
    assert fact_repository.calls[0][2] == result["fact_snapshot_id"]
    assert snapshot_repository.calls == [
        ("fact", "recruiting", {"fact_snapshot_id": result["fact_snapshot_id"]})
    ]
    assert outbox_repository.calls[0][0]["event_type"] == "fact_ingested"
    assert outbox_repository.calls[0][0]["payload"]["fact_snapshot_id"] == result["fact_snapshot_id"]
    assert outbox_repository.calls[0][0]["payload"]["affected_entity_types"] == [
        "job_posting",
        "company",
    ]
    assert outbox_repository.calls[0][0]["payload"]["scope"] == "shared"
