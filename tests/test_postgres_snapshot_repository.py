from __future__ import annotations

from typing import Any

from wiki_mcp.storage.postgres.repositories import PostgresSnapshotRepository


class FakeCursor:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self.results = list(results or [])
        self.executed: list[tuple[str, object]] = []
        self.rowcount = 0
        self._current_result: dict[str, Any] = {}

    def execute(self, query: str, params: object | None = None) -> None:
        self.executed.append((query, params))
        self._current_result = self.results.pop(0) if self.results else {}

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


def test_get_snapshot_status_qualifies_domain_and_layer_columns() -> None:
    cursor = FakeCursor([{"fetchone": None}])
    repository = PostgresSnapshotRepository(FakeConnection(cursor))

    repository.get_snapshot_status(domain="recruiting", layer="interpretation")

    query, params = cursor.executed[0]
    assert "WHERE p.domain = %s AND p.layer = %s" in query
    assert params == ["recruiting", "interpretation"]


def test_get_snapshot_status_returns_domain_registry_when_layer_is_omitted() -> None:
    cursor = FakeCursor(
        [
            {
                "fetchall": [
                    {
                        "layer": "fact",
                        "domain": "recruiting",
                        "current_snapshot_id": "fact_snap:seed",
                        "fact_snapshot_id": "fact_snap:seed",
                        "interpretation_snapshot_id": None,
                        "profile_version": None,
                        "published_at": "2026-04-18T00:00:00Z",
                    },
                    {
                        "layer": "interpretation",
                        "domain": "recruiting",
                        "current_snapshot_id": "interp_snap:seed",
                        "fact_snapshot_id": "fact_snap:seed",
                        "interpretation_snapshot_id": "interp_snap:seed",
                        "profile_version": None,
                        "published_at": "2026-04-18T00:10:00Z",
                    },
                ]
            }
        ]
    )
    repository = PostgresSnapshotRepository(FakeConnection(cursor))

    status = repository.get_snapshot_status(domain="recruiting", layer=None)

    assert status == {
        "domain": "recruiting",
        "layers": {
            "fact": {
                "layer": "fact",
                "domain": "recruiting",
                "current_snapshot_id": "fact_snap:seed",
                "fact_snapshot_id": "fact_snap:seed",
                "published_at": "2026-04-18T00:00:00Z",
            },
            "interpretation": {
                "layer": "interpretation",
                "domain": "recruiting",
                "current_snapshot_id": "interp_snap:seed",
                "fact_snapshot_id": "fact_snap:seed",
                "interpretation_snapshot_id": "interp_snap:seed",
                "published_at": "2026-04-18T00:10:00Z",
            },
        },
    }
