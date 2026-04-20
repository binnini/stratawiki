from __future__ import annotations

import json
from typing import Any

import pytest

from wiki_mcp.services.personal_assets import PersonalAssetConflictError
from wiki_mcp.storage.postgres.repositories import (
    PostgresPersonalAssetRepository,
    PostgresPersonalRepository,
)


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


def test_search_by_anchors_queries_anchor_metadata_column() -> None:
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

    records = repository.search_by_anchors(
        domain="recruiting",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        interpretation_ids=["interp:1"],
        fact_ids=["fact:1"],
        limit=5,
    )

    assert records[0]["id"] == "personal:1"
    query, params = cursor.executed[0]
    assert "jsonb_array_elements" in query
    assert "anchors_json" in query
    assert isinstance(params, list)
    assert params[-1] == 5


def test_list_records_maps_document_version_metadata_from_provenance() -> None:
    cursor = FakeCursor(
        [
            {
                "fetchall": [
                    {
                        "id": "pdoc_1",
                        "domain": "recruiting",
                        "kind": "note",
                        "title": "Prep",
                        "summary": "Prep summary",
                        "scope": "user",
                        "tenant_id": "tenant-1",
                        "user_id": "user-1",
                        "fact_snapshot_id": "fact_snap:1",
                        "interpretation_snapshot_id": "interp_snap:1",
                        "profile_version": "profile:v1",
                        "body_path": "wiki/users/user-1/personal-documents/pdoc_1.md",
                        "status": "active",
                        "schema_version": "personal.document.v1",
                        "updated_at": "2026-04-20T00:00:00Z",
                        "anchors_json": [],
                        "provenance_json": {
                            "generated_by": {"kind": "user"},
                            "_personal_document": {
                                "subspace": "raw",
                                "asset_refs": [],
                                "version": 3,
                                "created_at": "2026-04-19T23:59:00Z",
                            },
                        },
                    }
                ]
            }
        ]
    )
    repository = PostgresPersonalRepository(FakeConnection(cursor))

    records = repository.list_records(
        domain="recruiting",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        statuses=["active"],
        limit=10,
    )

    assert records[0]["version"] == 3
    assert records[0]["created_at"] == "2026-04-19T23:59:00Z"
    assert records[0]["updated_at"] == "2026-04-20T00:00:00Z"
    query, params = cursor.executed[0]
    assert "updated_at" in query
    assert isinstance(params, list)
    assert params[-1] == 10

def test_create_personal_asset_record_persists_metadata() -> None:
    cursor = FakeCursor(
        [
            {"fetchone": None},
            {
                "fetchone": {
                    "asset_id": "passet_abc123",
                    "domain": "recruiting",
                    "tenant_id": "tenant-1",
                    "user_id": "user-1",
                    "asset_kind": "file",
                    "media_type": "application/pdf",
                    "filename": "resume.pdf",
                    "blob_sha256": "sha256:abc123",
                    "size_bytes": 248192,
                    "storage_ref": "s3://bucket/resume.pdf",
                    "identity_key": "recruiting:tenant-1:user-1:sha256:abc123",
                    "status": "active",
                    "extraction_status": "not_requested",
                    "schema_version": "personal_asset.v1",
                    "created_at": "2026-04-20T00:00:00Z",
                    "updated_at": "2026-04-20T00:00:00Z",
                }
            },
        ]
    )
    repository = PostgresPersonalAssetRepository(FakeConnection(cursor))

    record = repository.create_record(
        {
            "asset_id": "passet_abc123",
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "asset_kind": "file",
            "media_type": "application/pdf",
            "filename": "resume.pdf",
            "blob_sha256": "sha256:abc123",
            "size_bytes": 248192,
            "storage_ref": "s3://bucket/resume.pdf",
            "identity_key": "recruiting:tenant-1:user-1:sha256:abc123",
            "status": "active",
            "extraction_status": "not_requested",
            "schema_version": "personal_asset.v1",
        }
    )

    assert record["asset_id"] == "passet_abc123"
    assert record["storage_ref"] == "s3://bucket/resume.pdf"
    assert "personal.asset" in cursor.executed[1][0]


def test_create_personal_asset_record_reports_conflict_with_existing_asset_id() -> None:
    cursor = FakeCursor(
        [
            {"fetchone": {"asset_id": "passet_existing"}},
        ]
    )
    repository = PostgresPersonalAssetRepository(FakeConnection(cursor))

    with pytest.raises(PersonalAssetConflictError) as exc_info:
        repository.create_record(
            {
                "asset_id": "passet_new",
                "domain": "recruiting",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "asset_kind": "file",
                "media_type": "application/pdf",
                "filename": "resume.pdf",
                "storage_ref": "s3://bucket/resume.pdf",
                "identity_key": "recruiting:tenant-1:user-1:s3://bucket/resume.pdf",
                "status": "active",
                "extraction_status": "not_requested",
                "schema_version": "personal_asset.v1",
            }
        )

    assert exc_info.value.details["asset_id"] == "passet_existing"
