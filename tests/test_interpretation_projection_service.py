from __future__ import annotations

from pathlib import Path

from psycopg import Connection

from wiki_mcp.services.interpretation_projection import (
    DefaultInterpretationProjectionService,
)
from wiki_mcp.storage.filesystem.rendering import (
    FilesystemAndPostgresRenderingRepository,
)
from wiki_mcp.storage.postgres.repositories import (
    PostgresDependencyRepository,
    PostgresFactRepository,
    PostgresInterpretationRepository,
    PostgresOutboxRepository,
    PostgresSnapshotRepository,
)


class StubFactRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: dict[str, str],
    ) -> list[dict[str, object]]:
        self.calls.append((ids, scope_ref))
        return [
            {
                "id": "fact:job_posting:emp-1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job_posting:emp-1",
                "attributes": {
                    "title": "Backend Engineer",
                    "company_name": "JobsWiki",
                    "employment_type": "full_time",
                },
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": "EMP-1"},
            },
            {
                "id": "fact:company:jobswiki",
                "domain": "recruiting",
                "entity_type": "company",
                "canonical_key": "company-name:jobswiki",
                "attributes": {"name": "JobsWiki"},
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": "EMP-1"},
            },
            {
                "id": "fact:job:backend",
                "domain": "recruiting",
                "entity_type": "job",
                "canonical_key": "job-name:backend-engineer",
                "attributes": {"name": "Backend Engineer"},
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": "EMP-1"},
            },
            {
                "id": "fact:section:1",
                "domain": "recruiting",
                "entity_type": "recruitment_section",
                "canonical_key": "recruitment_section:EMP-1:requirements:1",
                "attributes": {
                    "title": "Requirements",
                    "career_requirement": "3+ years backend development",
                    "education_requirement": "BS in Computer Science or equivalent",
                    "other_requirement": "Distributed systems experience",
                    "openings": "2",
                },
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": "EMP-1"},
            },
        ]


class StubInterpretationRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict[str, object]], dict[str, str]]] = []

    def save_records(
        self,
        records: list[dict[str, object]],
        snapshot_ref: dict[str, str],
    ) -> list[str]:
        self.calls.append((records, snapshot_ref))
        return [record["id"] for record in records]


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
        return snapshot_ref.get("interpretation_snapshot_id", snapshot_ref["fact_snapshot_id"])


class StubDependencyRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def replace_edges_for_target(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


class StubOutboxRepository:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, object]]] = []

    def append_events(self, events: list[dict[str, object]]) -> list[str]:
        self.calls.append(events)
        return ["evt-2"]


class StubRenderingRepository:
    def __init__(self) -> None:
        self.artifacts: list[dict[str, object]] = []

    def write_artifact(self, artifact: dict[str, object]) -> str:
        self.artifacts.append(artifact)
        return artifact["path"]  # type: ignore[return-value]


def test_project_fact_event_persists_interpretation_snapshot_and_dependencies() -> None:
    fact_repository = StubFactRepository()
    interpretation_repository = StubInterpretationRepository()
    snapshot_repository = StubSnapshotRepository()
    dependency_repository = StubDependencyRepository()
    rendering_repository = StubRenderingRepository()
    outbox_repository = StubOutboxRepository()
    service = DefaultInterpretationProjectionService(
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        dependency_repository=dependency_repository,
        rendering_repository=rendering_repository,
        outbox_repository=outbox_repository,
    )

    result = service.project_fact_event(
        {
            "id": "evt-1",
            "event_type": "fact_ingested",
            "aggregate_layer": "fact",
            "aggregate_id": "fact_snap:recruiting:EMP-1:123",
            "payload": {
                "domain": "recruiting",
                "source_id": "EMP-1",
                "connector": "worknet",
                "fact_snapshot_id": "fact_snap:recruiting:EMP-1:123",
                "affected_fact_ids": [
                    "fact:job_posting:emp-1",
                    "fact:company:jobswiki",
                    "fact:job:backend",
                    "fact:section:1",
                ],
                "affected_entity_types": [
                    "job_posting",
                    "company",
                    "job",
                    "recruitment_section",
                ],
                "scope": "shared",
                "facts_created": 4,
                "facts_updated": 0,
                "relations_created": 3,
            },
            "status": "claimed",
            "attempt_count": 1,
            "available_at": "2026-04-16T00:00:00Z",
            "claimed_at": "2026-04-16T00:01:00Z",
            "processed_at": None,
            "last_error": None,
            "idempotency_key": "fact_ingested:fact_snap:recruiting:EMP-1:123",
        }
    )

    assert fact_repository.calls == [
        (
            [
                "fact:job_posting:emp-1",
                "fact:company:jobswiki",
                "fact:job:backend",
                "fact:section:1",
            ],
            {"scope": "shared"},
        )
    ]
    saved_records = interpretation_repository.calls[0][0]
    saved_record_ids = [record["id"] for record in saved_records]
    hiring_record = next(
        record for record in saved_records if record["kind"] == "company_hiring_pattern"
    )
    candidate_profile_record = next(
        record
        for record in saved_records
        if record["kind"] == "company_candidate_profile_pattern"
    )
    assert hiring_record["subject_id"] == "company-name:jobswiki"
    assert "actively hiring" in hiring_record["body"]["summary"]
    assert candidate_profile_record["subject_id"] == "company-name:jobswiki"
    assert "candidate profile" in candidate_profile_record["body"]["summary"]
    assert candidate_profile_record["body"]["career_requirement_count"] == 1
    assert snapshot_repository.calls[0][0] == "interpretation"
    assert snapshot_repository.calls[0][2]["fact_snapshot_id"] == "fact_snap:recruiting:EMP-1:123"
    assert result["interpretation_ids"] == saved_record_ids
    assert result["emitted_outbox_event_ids"] == ["evt-2"]
    assert len(dependency_repository.calls) == 2
    assert dependency_repository.calls[0]["to_layer"] == "interpretation"
    assert len(dependency_repository.calls[0]["edges"]) == 4
    assert len(rendering_repository.artifacts) == 2
    assert rendering_repository.artifacts[0]["layer"] == "interpretation"
    artifact_paths = {artifact["path"] for artifact in rendering_repository.artifacts}
    assert artifact_paths == {
        "wiki/shared/recruiting/company_hiring_pattern/company-name__jobswiki.md",
        "wiki/shared/recruiting/company_candidate_profile_pattern/company-name__jobswiki.md",
    }
    candidate_profile_artifact = next(
        artifact
        for artifact in rendering_repository.artifacts
        if artifact["record_id"] == candidate_profile_record["id"]
    )
    assert "## Section Signals" in candidate_profile_artifact["body_markdown"]
    assert len(outbox_repository.calls[0]) == 2
    assert outbox_repository.calls[0][0]["event_type"] == "interpretation_snapshot_published"
    assert outbox_repository.calls[0][0]["payload"]["scope"] == "shared"
    assert {
        event["payload"]["interpretation_kind"] for event in outbox_repository.calls[0]
    } == {"company_hiring_pattern", "company_candidate_profile_pattern"}


def test_project_fact_event_rejects_incomplete_payload() -> None:
    service = DefaultInterpretationProjectionService(
        fact_repository=StubFactRepository(),
        interpretation_repository=StubInterpretationRepository(),
        snapshot_repository=StubSnapshotRepository(),
        dependency_repository=StubDependencyRepository(),
        rendering_repository=StubRenderingRepository(),
        outbox_repository=StubOutboxRepository(),
    )

    try:
        service.project_fact_event(
            {
                "id": "evt-1",
                "event_type": "fact_ingested",
                "aggregate_layer": "fact",
                "aggregate_id": "fact_snap:1",
                "payload": {"domain": "recruiting"},
                "status": "claimed",
                "attempt_count": 1,
                "available_at": "2026-04-16T00:00:00Z",
                "claimed_at": None,
                "processed_at": None,
                "last_error": None,
                "idempotency_key": None,
            }
        )
    except ValueError as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("Expected ValueError for incomplete fact_ingested payload")


def test_project_fact_event_skips_candidate_profile_family_without_requirement_signals() -> None:
    fact_repository = StubFactRepository()
    interpretation_repository = StubInterpretationRepository()
    snapshot_repository = StubSnapshotRepository()
    dependency_repository = StubDependencyRepository()
    rendering_repository = StubRenderingRepository()
    outbox_repository = StubOutboxRepository()
    service = DefaultInterpretationProjectionService(
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        dependency_repository=dependency_repository,
        rendering_repository=rendering_repository,
        outbox_repository=outbox_repository,
    )

    fact_repository.get_by_ids = lambda ids, scope_ref: [  # type: ignore[method-assign]
        {
            "id": "fact:job_posting:emp-1",
            "domain": "recruiting",
            "entity_type": "job_posting",
            "canonical_key": "job_posting:emp-1",
            "attributes": {
                "title": "Backend Engineer",
                "company_name": "JobsWiki",
                "employment_type": "full_time",
            },
            "scope": "shared",
            "schema_version": "v1",
            "provenance": {"source_id": "EMP-1"},
        },
        {
            "id": "fact:company:jobswiki",
            "domain": "recruiting",
            "entity_type": "company",
            "canonical_key": "company-name:jobswiki",
            "attributes": {"name": "JobsWiki"},
            "scope": "shared",
            "schema_version": "v1",
            "provenance": {"source_id": "EMP-1"},
        },
        {
            "id": "fact:section:1",
            "domain": "recruiting",
            "entity_type": "recruitment_section",
            "canonical_key": "recruitment_section:EMP-1:requirements:1",
            "attributes": {"title": "Requirements"},
            "scope": "shared",
            "schema_version": "v1",
            "provenance": {"source_id": "EMP-1"},
        },
    ]

    result = service.project_fact_event(
        {
            "id": "evt-1",
            "event_type": "fact_ingested",
            "aggregate_layer": "fact",
            "aggregate_id": "fact_snap:recruiting:EMP-1:123",
            "payload": {
                "domain": "recruiting",
                "source_id": "EMP-1",
                "connector": "worknet",
                "fact_snapshot_id": "fact_snap:recruiting:EMP-1:123",
                "affected_fact_ids": [
                    "fact:job_posting:emp-1",
                    "fact:company:jobswiki",
                    "fact:section:1",
                ],
                "affected_entity_types": [
                    "job_posting",
                    "company",
                    "recruitment_section",
                ],
                "scope": "shared",
                "facts_created": 3,
                "facts_updated": 0,
                "relations_created": 0,
            },
            "status": "claimed",
            "attempt_count": 1,
            "available_at": "2026-04-16T00:00:00Z",
            "claimed_at": "2026-04-16T00:01:00Z",
            "processed_at": None,
            "last_error": None,
            "idempotency_key": "fact_ingested:fact_snap:recruiting:EMP-1:123",
        }
    )

    assert result["interpretation_ids"] == ["interp:company_hiring_pattern:company-name:jobswiki"]
    assert len(rendering_repository.artifacts) == 1
    assert len(outbox_repository.calls[0]) == 1


def test_project_fact_event_writes_shared_rendered_page_to_postgres_and_filesystem(
    postgres_connection: Connection[dict],
    tmp_path: Path,
) -> None:
    fact_repository = PostgresFactRepository(postgres_connection)
    interpretation_repository = PostgresInterpretationRepository(postgres_connection)
    snapshot_repository = PostgresSnapshotRepository(postgres_connection)
    dependency_repository = PostgresDependencyRepository(postgres_connection)
    rendering_repository = FilesystemAndPostgresRenderingRepository(
        tmp_path,
        postgres_connection,
    )
    outbox_repository = PostgresOutboxRepository(postgres_connection)

    fact_repository.write_facts(
        [
            {
                "id": "fact:job_posting:emp-1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job_posting:emp-1",
                "attributes": {
                    "title": "Backend Engineer",
                    "company_name": "JobsWiki",
                    "employment_type": "full_time",
                },
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": "EMP-1"},
            },
            {
                "id": "fact:company:jobswiki",
                "domain": "recruiting",
                "entity_type": "company",
                "canonical_key": "company-name:jobswiki",
                "attributes": {"name": "JobsWiki"},
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": "EMP-1"},
            },
            {
                "id": "fact:job:backend",
                "domain": "recruiting",
                "entity_type": "job",
                "canonical_key": "job-name:backend-engineer",
                "attributes": {"name": "Backend Engineer"},
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": "EMP-1"},
            },
            {
                "id": "fact:section:1",
                "domain": "recruiting",
                "entity_type": "recruitment_section",
                "canonical_key": "recruitment_section:EMP-1:requirements:1",
                "attributes": {
                    "title": "Requirements",
                    "career_requirement": "3+ years backend development",
                    "education_requirement": "BS in Computer Science or equivalent",
                    "other_requirement": "Distributed systems experience",
                    "openings": "2",
                },
                "scope": "shared",
                "schema_version": "v1",
                "provenance": {"source_id": "EMP-1"},
            },
        ],
        [],
    )

    service = DefaultInterpretationProjectionService(
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        dependency_repository=dependency_repository,
        rendering_repository=rendering_repository,
        outbox_repository=outbox_repository,
    )

    result = service.project_fact_event(
        {
            "id": "evt-1",
            "event_type": "fact_ingested",
            "aggregate_layer": "fact",
            "aggregate_id": "fact_snap:recruiting:EMP-1:123",
            "payload": {
                "domain": "recruiting",
                "source_id": "EMP-1",
                "connector": "worknet",
                "fact_snapshot_id": "fact_snap:recruiting:EMP-1:123",
                "affected_fact_ids": [
                    "fact:job_posting:emp-1",
                    "fact:company:jobswiki",
                    "fact:job:backend",
                    "fact:section:1",
                ],
                "affected_entity_types": [
                    "job_posting",
                    "company",
                    "job",
                    "recruitment_section",
                ],
                "scope": "shared",
                "facts_created": 4,
                "facts_updated": 0,
                "relations_created": 0,
            },
            "status": "claimed",
            "attempt_count": 1,
            "available_at": "2026-04-16T00:00:00Z",
            "claimed_at": "2026-04-16T00:01:00Z",
            "processed_at": None,
            "last_error": None,
            "idempotency_key": "fact_ingested:fact_snap:recruiting:EMP-1:123",
        }
    )

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT layer, record_id, path, fact_snapshot_id, interpretation_snapshot_id, metadata_json
            FROM graph.rendered_page
            WHERE layer = %s
            ORDER BY path
            """,
            ("interpretation",),
        )
        rows = cursor.fetchall()

    assert len(rows) == 2
    row_by_path = {row["path"]: row for row in rows}
    hiring_row = row_by_path[
        "wiki/shared/recruiting/company_hiring_pattern/company-name__jobswiki.md"
    ]
    candidate_profile_row = row_by_path[
        "wiki/shared/recruiting/company_candidate_profile_pattern/company-name__jobswiki.md"
    ]

    assert hiring_row["record_id"] in result["interpretation_ids"]
    assert hiring_row["fact_snapshot_id"] == "fact_snap:recruiting:EMP-1:123"
    assert hiring_row["interpretation_snapshot_id"] == result["interpretation_snapshot_id"]
    assert hiring_row["metadata_json"]["title"] == "JobsWiki hiring pattern"
    assert (
        (tmp_path / hiring_row["path"]).read_text(encoding="utf-8").startswith(
            "# JobsWiki hiring pattern\n"
        )
    )
    assert candidate_profile_row["record_id"] in result["interpretation_ids"]
    assert candidate_profile_row["interpretation_snapshot_id"] == result["interpretation_snapshot_id"]
    assert candidate_profile_row["metadata_json"]["title"] == "JobsWiki candidate profile pattern"
    assert "## Section Signals" in (
        tmp_path / candidate_profile_row["path"]
    ).read_text(encoding="utf-8")
