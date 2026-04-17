from __future__ import annotations

from wiki_mcp.storage.postgres.repositories import PostgresInterpretationRepository


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, object]] = []
        self.rowcount = 0

    def execute(self, query: str, params: object | None = None) -> None:
        self.executed.append((query, params))
        self.rowcount = len(self.rows)

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


def test_search_for_retrieval_only_queries_published_and_stale_records() -> None:
    cursor = FakeCursor([])
    repository = PostgresInterpretationRepository(FakeConnection(cursor))

    repository.search_for_retrieval(
        domain="recruiting",
        scope_ref={"scope": "shared"},
        query_text="llm experience",
        query_tokens=["llm", "experience"],
        limit=5,
    )

    query, params = cursor.executed[0]
    assert "status IN ('published', 'stale')" in query
    assert params == ["recruiting", "shared", "llm experience", "llm experience", 5]
