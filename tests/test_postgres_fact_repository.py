from __future__ import annotations

from wiki_mcp.storage.postgres.repositories import PostgresFactRepository


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, object]] = []
        self.rowcount = 0

    def execute(self, query: str, params: object | None = None) -> None:
        self.executed.append((query, params))
        self.rowcount = len(self.rows)

    def fetchone(self) -> object:
        if not self.rows:
            return None
        return self.rows[0]

    def fetchall(self) -> list[dict[str, object]]:
        return list(self.rows)


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


def test_get_by_canonical_keys_queries_fact_store() -> None:
    cursor = FakeCursor(
        [
            {
                "id": "fact:job_posting:emp-1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job_posting:EMP-1",
                "scope": "shared",
                "fact_snapshot_id": "fact_snap:recruiting:EMP-1:1",
                "tenant_id": None,
                "user_id": None,
                "schema_version": "v1",
                "attributes_json": {"title": "Backend Engineer"},
                "provenance_json": {"source_id": "EMP-1"},
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

    query, params = cursor.executed[0]
    assert "WHERE canonical_key = ANY(%s)" in query
    assert params == [["job_posting:EMP-1"], "shared"]

