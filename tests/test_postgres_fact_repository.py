from __future__ import annotations

from typing import Any

import pytest

from wiki_mcp.storage.postgres.repositories import PostgresFactRepository


class FakeCursor:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self.results = list(results or [])
        self.executed: list[tuple[str, object]] = []
        self.rowcount = 0
        self._current_result: dict[str, Any] = {}

    def execute(self, query: str, params: object | None = None) -> None:
        self.executed.append((query, params))
        self._current_result = self.results.pop(0) if self.results else {}
        rowcount = self._current_result.get("rowcount")
        if isinstance(rowcount, int):
            self.rowcount = rowcount
            return
        fetchall = self._current_result.get("fetchall")
        if isinstance(fetchall, list):
            self.rowcount = len(fetchall)
            return
        self.rowcount = 1 if self._current_result.get("fetchone") is not None else 0

    def fetchone(self) -> object:
        return self._current_result.get("fetchone")

    def fetchall(self) -> list[dict[str, object]]:
        fetchall = self._current_result.get("fetchall")
        return list(fetchall) if isinstance(fetchall, list) else []


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_get_by_canonical_keys_queries_fact_store_and_maps_metadata() -> None:
    cursor = FakeCursor(
        [
            {
                "fetchall": [
                    {
                        "id": "fact:job_posting:emp-1",
                        "layer": "fact",
                        "domain": "recruiting",
                        "entity_type": "job_posting",
                        "canonical_key": "job_posting:EMP-1",
                        "scope": "shared",
                        "fact_snapshot_id": "fact_snap:recruiting:EMP-1:1",
                        "tenant_id": None,
                        "user_id": None,
                        "status": "active",
                        "version": 2,
                        "created_at": "2026-04-18T00:00:00Z",
                        "updated_at": "2026-04-18T01:00:00Z",
                        "schema_version": "fact.v1",
                        "attributes_json": {"title": "Backend Engineer"},
                        "provenance_json": {"source_id": "EMP-1"},
                    }
                ]
            }
        ]
    )
    repository = PostgresFactRepository(FakeConnection(cursor))

    records = repository.get_by_canonical_keys(
        ["job_posting:EMP-1"],
        {"scope": "shared"},
    )

    assert len(records) == 1
    assert records[0]["id"] == "fact:job_posting:emp-1"
    assert records[0]["canonical_key"] == "job_posting:EMP-1"
    assert records[0]["layer"] == "fact"
    assert records[0]["status"] == "active"
    assert records[0]["version"] == 2
    assert records[0]["created_at"] == "2026-04-18T00:00:00Z"
    assert records[0]["updated_at"] == "2026-04-18T01:00:00Z"

    query, params = cursor.executed[0]
    assert "WHERE canonical_key = ANY(%s)" in query
    assert params == [["job_posting:EMP-1"], "shared"]


def test_get_by_ids_decodes_text_rows_returned_as_bytes() -> None:
    cursor = FakeCursor(
        [
            {
                "fetchall": [
                    {
                        "id": b"fact:job_posting:emp-1",
                        "layer": b"fact",
                        "domain": b"recruiting",
                        "entity_type": b"job_posting",
                        "canonical_key": b"job_posting:EMP-1",
                        "scope": b"shared",
                        "fact_snapshot_id": b"fact_snap:recruiting:EMP-1:1",
                        "tenant_id": None,
                        "user_id": None,
                        "status": b"active",
                        "version": 2,
                        "created_at": "2026-04-18T00:00:00Z",
                        "updated_at": "2026-04-18T01:00:00Z",
                        "schema_version": b"fact.v1",
                        "attributes_json": {"title": "Backend Engineer"},
                        "provenance_json": {"source_id": "EMP-1"},
                    }
                ]
            }
        ]
    )
    repository = PostgresFactRepository(FakeConnection(cursor))

    records = repository.get_by_ids(
        ["fact:job_posting:emp-1"],
        {"scope": "shared"},
    )

    assert records[0]["id"] == "fact:job_posting:emp-1"
    assert records[0]["layer"] == "fact"
    assert records[0]["canonical_key"] == "job_posting:EMP-1"


def test_write_facts_defaults_fact_metadata_on_insert() -> None:
    cursor = FakeCursor(
        [
            {"fetchone": None},
            {"fetchone": None},
            {"fetchone": {"inserted": True}},
        ]
    )
    repository = PostgresFactRepository(FakeConnection(cursor))

    result = repository.write_facts(
        [
            {
                "id": "fact:job_posting:emp-1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job_posting:EMP-1",
                "attributes": {"title": "Backend Engineer"},
                "scope": "shared",
                "schema_version": "fact.v1",
                "provenance": {"source_id": "EMP-1"},
            }
        ],
        [],
        fact_snapshot_id="fact_snap:recruiting:EMP-1:1",
    )

    assert result["facts_created"] == 1
    assert result["facts_updated"] == 0
    insert_query, insert_params = cursor.executed[2]
    assert "INSERT INTO fact.record_envelopes" in insert_query
    assert insert_query.count("%s") == len(insert_params)
    assert insert_params[1] == "fact"
    assert insert_params[9] == "active"
    assert insert_params[10] == 1
    assert insert_params[11]
    assert insert_params[12]


def test_write_facts_increments_version_on_update() -> None:
    cursor = FakeCursor(
        [
            {
                "fetchone": {
                    "id": "fact:job_posting:emp-1",
                    "layer": "fact",
                    "domain": "recruiting",
                    "entity_type": "job_posting",
                    "canonical_key": "job_posting:EMP-1",
                    "scope": "shared",
                    "fact_snapshot_id": "fact_snap:recruiting:EMP-1:old",
                    "tenant_id": None,
                    "user_id": None,
                    "status": "active",
                    "version": 2,
                    "created_at": "2026-04-18T00:00:00Z",
                    "updated_at": "2026-04-18T01:00:00Z",
                    "schema_version": "fact.v1",
                    "attributes_json": {"title": "Old title"},
                    "provenance_json": {"source_id": "EMP-1"},
                }
            },
            {
                "fetchone": {
                    "id": "fact:job_posting:emp-1",
                    "layer": "fact",
                    "domain": "recruiting",
                    "entity_type": "job_posting",
                    "canonical_key": "job_posting:EMP-1",
                    "scope": "shared",
                    "fact_snapshot_id": "fact_snap:recruiting:EMP-1:old",
                    "tenant_id": None,
                    "user_id": None,
                    "status": "active",
                    "version": 2,
                    "created_at": "2026-04-18T00:00:00Z",
                    "updated_at": "2026-04-18T01:00:00Z",
                    "schema_version": "fact.v1",
                    "attributes_json": {"title": "Old title"},
                    "provenance_json": {"source_id": "EMP-1"},
                }
            },
            {"fetchone": {"inserted": False}},
        ]
    )
    repository = PostgresFactRepository(FakeConnection(cursor))

    result = repository.write_facts(
        [
            {
                "id": "fact:job_posting:emp-1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job_posting:EMP-1",
                "attributes": {"title": "Backend Engineer"},
                "scope": "shared",
                "schema_version": "fact.v1",
                "provenance": {"source_id": "EMP-1"},
            }
        ],
        [],
        fact_snapshot_id="fact_snap:recruiting:EMP-1:new",
    )

    assert result["facts_created"] == 0
    assert result["facts_updated"] == 1
    _, insert_params = cursor.executed[2]
    assert insert_params[10] == 3
    assert insert_params[11] == "2026-04-18T00:00:00Z"


def test_write_facts_rejects_canonical_identity_conflict_at_storage_boundary() -> None:
    cursor = FakeCursor(
        [
            {"fetchone": None},
            {
                "fetchone": {
                    "id": "fact:job_posting:existing",
                    "layer": "fact",
                    "domain": "recruiting",
                    "entity_type": "job_posting",
                    "canonical_key": "job_posting:EMP-1",
                    "scope": "shared",
                    "fact_snapshot_id": "fact_snap:recruiting:EMP-1:old",
                    "tenant_id": None,
                    "user_id": None,
                    "status": "active",
                    "version": 1,
                    "created_at": "2026-04-18T00:00:00Z",
                    "updated_at": "2026-04-18T01:00:00Z",
                    "schema_version": "fact.v1",
                    "attributes_json": {"title": "Backend Engineer"},
                    "provenance_json": {"source_id": "EMP-1"},
                }
            },
        ]
    )
    connection = FakeConnection(cursor)
    repository = PostgresFactRepository(connection)

    with pytest.raises(ValueError, match="Canonical Fact identity conflict at storage boundary"):
        repository.write_facts(
            [
                {
                    "id": "fact:job_posting:new",
                    "domain": "recruiting",
                    "entity_type": "job_posting",
                    "canonical_key": "job_posting:EMP-1",
                    "attributes": {"title": "Backend Engineer"},
                    "scope": "shared",
                    "schema_version": "fact.v1",
                    "provenance": {"source_id": "EMP-1"},
                }
            ],
            [],
            fact_snapshot_id="fact_snap:recruiting:EMP-1:new",
        )

    assert connection.rollbacks == 1


def test_search_for_retrieval_uses_token_or_query_for_postgres_fts() -> None:
    cursor = FakeCursor([{"fetchall": []}])
    repository = PostgresFactRepository(FakeConnection(cursor))

    repository.search_for_retrieval(
        domain="recruiting",
        scope_ref={"scope": "shared"},
        query_text="backend roles in tokyo startups",
        query_tokens=["backend", "tokyo", "startups"],
        limit=5,
    )

    query, params = cursor.executed[0]
    assert "to_tsquery('simple', %s)" in query
    assert "backend | tokyo | startups" in params
