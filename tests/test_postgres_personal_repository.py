from __future__ import annotations

import json
from typing import Any

from wiki_mcp.storage.postgres.repositories import PostgresPersonalRepository


class FakeCursor:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self.results = list(results or [])
        self.executed: list[tuple[str, object]] = []
        self.rowcount = 0
        self._current_result: dict[str, Any] = {}

    def execute(self, query: str, params: object | None = None) -> None:
        self.executed.append((query, params))
        self._current_result = self.results.pop(0) if self.results else {}
        fetchall = self._current_result.get("fetchall")
        if isinstance(fetchall, list):
            self.rowcount = len(fetchall)
        else:
            self.rowcount = 1

    def fetchall(self) -> list[dict[str, object]]:
        fetchall = self._current_result.get("fetchall")
        return list(fetchall) if isinstance(fetchall, list) else []

    def fetchone(self) -> object:
        return self._current_result.get("fetchone")


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


def test_get_by_ids_maps_personal_anchor_metadata() -> None:
    cursor = FakeCursor(
        [
            {
                "fetchall": [
                    {
                        "id": "personal:1",
                        "domain": "recruiting",
                        "kind": "query_answer",
                        "title": "Answer",
                        "summary": "Saved answer",
                        "scope": "user",
                        "tenant_id": "tenant-1",
                        "user_id": "user-1",
                        "fact_snapshot_id": "fact_snap:1",
                        "interpretation_snapshot_id": "interp_snap:1",
                        "profile_version": "profile:v1",
                        "body_path": "wiki/users/user-1/answers/answer.md",
                        "status": "active",
                        "schema_version": "personal.v1",
                        "anchors_json": [
                            {"layer": "interpretation", "id": "interp:1"},
                            {"layer": "fact", "id": "fact:1"},
                        ],
                        "provenance_json": {"generated_by": {"kind": "llm"}},
                    }
                ]
            }
        ]
    )
    repository = PostgresPersonalRepository(FakeConnection(cursor))

    records = repository.get_by_ids(
        ["personal:1"],
        {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert records == [
        {
            "id": "personal:1",
            "domain": "recruiting",
            "kind": "query_answer",
            "title": "Answer",
            "summary": "Saved answer",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:1",
                "interpretation_snapshot_id": "interp_snap:1",
                "profile_version": "profile:v1",
            },
            "profile_version": "profile:v1",
            "body_path": "wiki/users/user-1/answers/answer.md",
            "anchors": [
                {"layer": "interpretation", "id": "interp:1"},
                {"layer": "fact", "id": "fact:1"},
            ],
            "status": "active",
            "schema_version": "personal.v1",
            "provenance": {"generated_by": {"kind": "llm"}},
        }
    ]

    query, _ = cursor.executed[0]
    assert "anchors_json" in query


def test_save_record_persists_personal_anchor_metadata() -> None:
    cursor = FakeCursor()
    repository = PostgresPersonalRepository(FakeConnection(cursor))

    repository.save_record(
        {
            "id": "personal:1",
            "domain": "recruiting",
            "kind": "query_answer",
            "title": "Answer",
            "summary": "Saved answer",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:1",
                "interpretation_snapshot_id": "interp_snap:1",
                "profile_version": "profile:v1",
            },
            "profile_version": "profile:v1",
            "body_path": "wiki/users/user-1/answers/answer.md",
            "anchors": [
                {"layer": "interpretation", "id": "interp:1"},
                {"layer": "fact", "id": "fact:1"},
            ],
            "status": "active",
            "schema_version": "personal.v1",
            "provenance": {"generated_by": {"kind": "llm"}},
        }
    )

    query, params = cursor.executed[0]
    assert "anchors_json" in query
    assert isinstance(params, tuple)
    assert json.loads(params[14]) == [
        {"layer": "interpretation", "id": "interp:1"},
        {"layer": "fact", "id": "fact:1"},
    ]
