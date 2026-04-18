from __future__ import annotations

from wiki_mcp.storage.postgres.repositories import (
    PostgresFactRepository,
    PostgresInterpretationRepository,
    PostgresPersonalRepository,
    PostgresSnapshotRepository,
)


class FakeCursor:
    def __init__(self) -> None:
        self.queries: list[tuple[str, object]] = []
        self.rowcount = 1

    def execute(self, query: str, params: object | None = None) -> None:
        self.queries.append((query, params))

    def fetchone(self) -> dict[str, object]:
        return {"inserted": True}

    def fetchall(self) -> list[dict[str, object]]:
        return []


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_fact_repository_rejects_invalid_scope_shape() -> None:
    repository = PostgresFactRepository(FakeConnection())

    try:
        repository.write_facts(
            [
                {
                    "id": "fact:1",
                    "domain": "recruiting",
                    "entity_type": "job_posting",
                    "canonical_key": "job:1",
                    "attributes": {},
                    "scope": "shared",
                    "tenant_id": "tenant-1",
                    "schema_version": "fact.v1",
                    "provenance": {"source_id": "job:1"},
                }
            ],
            [],
            fact_snapshot_id="fact_snap:1",
        )
    except ValueError as exc:
        assert "shared scope" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid shared scope shape.")


def test_interpretation_repository_rejects_unknown_lifecycle_status() -> None:
    repository = PostgresInterpretationRepository(FakeConnection())

    try:
        repository.save_records(
            [
                {
                    "id": "interp:1",
                    "domain": "recruiting",
                    "family": "market_trend",
                    "kind": "trend",
                    "subject_type": "market_segment",
                    "subject_id": "backend-japan-midlevel",
                    "scope_ref": {"scope": "shared"},
                    "schema_version": "interpretation.v2",
                    "status": "active",
                    "confidence": 0.8,
                    "fact_snapshot_id": "fact_snap:1",
                    "computed_at": "2026-04-17T10:00:00Z",
                    "expires_at": None,
                    "body": {"summary": "test"},
                    "provenance": {"generated_by": {"kind": "llm"}},
                    "render_hints": {"page_family": "market_trend"},
                }
            ],
            {"fact_snapshot_id": "fact_snap:1"},
        )
    except ValueError as exc:
        assert "must be one of" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid interpretation status.")


def test_personal_repository_requires_user_scope_and_matching_profile_version() -> None:
    repository = PostgresPersonalRepository(FakeConnection())

    try:
        repository.save_record(
            {
                "id": "personal:1",
                "domain": "recruiting",
                "kind": "plan",
                "title": "Q2 plan",
                "summary": "summary",
                "scope_ref": {"scope": "tenant", "tenant_id": "tenant-1"},
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:1",
                    "profile_version": "profile_v1",
                },
                "profile_version": "profile_v2",
                "body_path": "personal/q2-plan.md",
                "status": "active",
                "schema_version": "personal.v1",
                "provenance": {"generated_by": {"kind": "user"}},
            }
        )
    except ValueError as exc:
        message = str(exc)
        assert "must use user scope" in message or "must include both tenant_id and user_id" in message
    else:
        raise AssertionError("Expected ValueError for invalid personal metadata.")


def test_personal_repository_rejects_invalid_anchor_shape() -> None:
    repository = PostgresPersonalRepository(FakeConnection())

    try:
        repository.save_record(
            {
                "id": "personal:1",
                "domain": "recruiting",
                "kind": "plan",
                "title": "Q2 plan",
                "summary": "summary",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:1",
                    "profile_version": "profile_v1",
                },
                "profile_version": "profile_v1",
                "body_path": "personal/q2-plan.md",
                "anchors": [{"layer": "personal", "id": "personal:2"}],
                "status": "active",
                "schema_version": "personal.v1",
                "provenance": {"generated_by": {"kind": "user"}},
            }
        )
    except ValueError as exc:
        assert "anchors[0].layer" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid personal anchor metadata.")


def test_snapshot_repository_rejects_empty_fact_snapshot_id() -> None:
    repository = PostgresSnapshotRepository(FakeConnection())

    try:
        repository.publish_snapshot(
            "fact",
            "recruiting",
            {"fact_snapshot_id": ""},
        )
    except ValueError as exc:
        assert "fact_snapshot_id" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid snapshot_ref.")
