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


def test_get_by_ids_maps_interpretation_snapshot_metadata() -> None:
    cursor = FakeCursor(
        [
            {
                "id": "interp:published:1",
                "domain": "recruiting",
                "family": "market_trend",
                "kind": "market_trend",
                "subject_type": "market_segment",
                "subject_id": "backend-japan-midlevel",
                "scope": "shared",
                "tenant_id": None,
                "user_id": None,
                "schema_version": "interpretation.v2",
                "status": "published",
                "confidence": 0.82,
                "fact_snapshot_id": "fact_snap:1",
                "interpretation_snapshot_id": "interp_snap:published:1",
                "computed_at": "2026-04-18T00:00:00Z",
                "expires_at": "2026-04-19T00:00:00Z",
                "title": "Demand is rising",
                "claim": "Production AI demand is rising.",
                "summary": "Demand is rising for backend roles.",
                "body_json": {"signals": ["llm"], "observations": [], "counterpoints": []},
                "evidence_json": [{"fact_id": "fact:job:1", "weight": 1.0, "role": "primary"}],
                "relations_json": [],
                "provenance_json": {"generated_by": {"kind": "llm"}},
                "render_hints_json": {"page_family": "market_trend"},
            }
        ]
    )
    repository = PostgresInterpretationRepository(FakeConnection(cursor))

    records = repository.get_by_ids(["interp:published:1"], {"scope": "shared"})

    assert records[0]["interpretation_snapshot_id"] == "interp_snap:published:1"
    query, params = cursor.executed[0]
    assert "interpretation_snapshot_id" in query
    assert params == [["interp:published:1"], "shared"]
