from __future__ import annotations

from psycopg import Connection

from wiki_mcp.storage.postgres.repositories import (
    PostgresDependencyRepository,
    PostgresFactRepository,
    PostgresInterpretationRepository,
    PostgresOutboxRepository,
    PostgresSnapshotRepository,
)


def _shared_fact_records() -> list[dict[str, object]]:
    return [
        {
            "id": "fact:job_posting:emp-1",
            "domain": "recruiting",
            "entity_type": "job_posting",
            "canonical_key": "job_posting:emp-1",
            "attributes": {"title": "Backend Engineer"},
            "scope": "shared",
            "schema_version": "v1",
            "provenance": {"source_id": "EMP-1"},
        },
        {
            "id": "fact:company:comp-1",
            "domain": "recruiting",
            "entity_type": "company",
            "canonical_key": "company:comp-1",
            "attributes": {"name": "JobsWiki"},
            "scope": "shared",
            "schema_version": "v1",
            "provenance": {"source_id": "EMP-1"},
        },
    ]


def _shared_relation() -> dict[str, object]:
    return {
        "domain": "recruiting",
        "relation_type": "posted_by",
        "from_canonical_key": "job_posting:emp-1",
        "to_canonical_key": "company:comp-1",
        "scope": "shared",
        "schema_version": "v1",
        "provenance": {"source_id": "EMP-1"},
        "attributes": {},
    }


def test_fact_repository_writes_and_updates_records_and_relations(
    postgres_connection: Connection[dict],
) -> None:
    repository = PostgresFactRepository(postgres_connection)
    records = _shared_fact_records()
    relations = [_shared_relation()]

    result = repository.write_facts(records, relations)

    assert result == {
        "facts_created": 2,
        "facts_updated": 0,
        "relations_created": 1,
        "affected_fact_ids": ["fact:job_posting:emp-1", "fact:company:comp-1"],
    }

    records[0]["attributes"] = {"title": "Senior Backend Engineer"}
    second_result = repository.write_facts(records, relations)

    assert second_result["facts_created"] == 0
    assert second_result["facts_updated"] == 2
    assert second_result["relations_created"] == 0

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT entity_type, canonical_key, scope, attributes_json
            FROM fact.record_envelopes
            ORDER BY entity_type
            """
        )
        stored_records = cursor.fetchall()
        cursor.execute("SELECT relation_type, scope FROM fact.relation_envelopes")
        stored_relations = cursor.fetchall()

    assert stored_records[0]["entity_type"] == "company"
    assert stored_records[1]["attributes_json"]["title"] == "Senior Backend Engineer"
    assert stored_relations == [{"relation_type": "posted_by", "scope": "shared"}]


def test_outbox_repository_uses_idempotency_keys(
    postgres_connection: Connection[dict],
) -> None:
    repository = PostgresOutboxRepository(postgres_connection)

    first_ids = repository.append_events(
        [
            {
                "event_type": "fact_ingested",
                "aggregate_layer": "fact",
                "aggregate_id": "fact_snap:1",
                "idempotency_key": "fact_ingested:fact_snap:1",
                "payload": {"fact_snapshot_id": "fact_snap:1"},
            }
        ]
    )
    second_ids = repository.append_events(
        [
            {
                "event_type": "fact_ingested",
                "aggregate_layer": "fact",
                "aggregate_id": "fact_snap:1",
                "idempotency_key": "fact_ingested:fact_snap:1",
                "payload": {"fact_snapshot_id": "fact_snap:1"},
            }
        ]
    )
    third_ids = repository.append_events(
        [
            {
                "event_type": "fact_ingested",
                "aggregate_layer": "fact",
                "aggregate_id": "fact_snap:2",
                "payload": {"fact_snapshot_id": "fact_snap:2"},
            }
        ]
    )

    assert first_ids == second_ids
    assert third_ids[0] != first_ids[0]

    with postgres_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM ops.outbox_event")
        row = cursor.fetchone()

    assert row["count"] == 2


def test_outbox_repository_claims_and_marks_events(
    postgres_connection: Connection[dict],
) -> None:
    repository = PostgresOutboxRepository(postgres_connection)
    [event_id] = repository.append_events(
        [
            {
                "event_type": "fact_ingested",
                "aggregate_layer": "fact",
                "aggregate_id": "fact_snap:1",
                "payload": {
                    "domain": "recruiting",
                    "source_id": "EMP-1",
                    "connector": "worknet",
                    "fact_snapshot_id": "fact_snap:1",
                    "affected_fact_ids": ["fact:job_posting:emp-1"],
                    "affected_entity_types": ["job_posting"],
                    "scope": "shared",
                    "facts_created": 1,
                    "facts_updated": 0,
                    "relations_created": 0,
                },
            }
        ]
    )

    claimed = repository.claim_pending(limit=10, event_types=["fact_ingested"])
    repository.mark_processed(event_id)

    assert claimed[0]["id"] == event_id
    assert claimed[0]["status"] == "claimed"
    assert claimed[0]["attempt_count"] == 1

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, processed_at IS NOT NULL AS processed FROM ops.outbox_event WHERE id = %s",
            (event_id,),
        )
        row = cursor.fetchone()

    assert row == {"status": "processed", "processed": True}


def test_snapshot_repository_tracks_pointer_and_publication_history(
    postgres_connection: Connection[dict],
) -> None:
    repository = PostgresSnapshotRepository(postgres_connection)

    first_snapshot_id = repository.publish_snapshot(
        "fact",
        "recruiting",
        {"fact_snapshot_id": "fact_snap:1"},
    )
    second_snapshot_id = repository.publish_snapshot(
        "fact",
        "recruiting",
        {"fact_snapshot_id": "fact_snap:2"},
    )

    assert first_snapshot_id == "fact_snap:1"
    assert second_snapshot_id == "fact_snap:2"

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_snapshot_id, fact_snapshot_id FROM ops.snapshot_pointer WHERE layer = %s AND domain = %s",
            ("fact", "recruiting"),
        )
        pointer = cursor.fetchone()
        cursor.execute(
            """
            SELECT snapshot_id
            FROM ops.snapshot_publication
            WHERE layer = %s AND domain = %s
            ORDER BY snapshot_id
            """,
            ("fact", "recruiting"),
        )
        publications = cursor.fetchall()

    assert pointer == {
        "current_snapshot_id": "fact_snap:2",
        "fact_snapshot_id": "fact_snap:2",
    }
    assert publications == [{"snapshot_id": "fact_snap:1"}, {"snapshot_id": "fact_snap:2"}]


def test_interpretation_repository_saves_records_with_fact_snapshot(
    postgres_connection: Connection[dict],
) -> None:
    repository = PostgresInterpretationRepository(postgres_connection)

    stored_ids = repository.save_records(
        [
            {
                "id": "interp:company_hiring_pattern:company-name:jobswiki",
                "domain": "recruiting",
                "kind": "company_hiring_pattern",
                "subject_type": "company",
                "subject_id": "company-name:jobswiki",
                "scope_ref": {"scope": "shared"},
                "schema_version": "v1",
                "status": "active",
                "confidence": 0.6,
                "computed_at": "2026-04-16T00:00:00Z",
                "expires_at": None,
                "body": {"summary": "JobsWiki is actively hiring."},
                "provenance": {"source_event_id": "evt-1"},
                "render_hints": {"template": "company_hiring_pattern"},
            }
        ],
        {"fact_snapshot_id": "fact_snap:1"},
    )

    loaded = repository.get_by_ids(stored_ids, {"scope": "shared"})

    assert stored_ids == ["interp:company_hiring_pattern:company-name:jobswiki"]
    assert loaded[0]["body"]["summary"] == "JobsWiki is actively hiring."


def test_dependency_repository_matches_rendered_pages_by_scope(
    postgres_connection: Connection[dict],
) -> None:
    repository = PostgresDependencyRepository(postgres_connection)

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO graph.dependency_edge (
                domain,
                from_layer,
                from_id,
                to_layer,
                to_id,
                scope,
                tenant_id,
                user_id,
                edge_type,
                attributes_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                "recruiting",
                "fact",
                "fact:job_posting:emp-1",
                "personal",
                "personal:plan-1",
                "user",
                "tenant-1",
                "user-1",
                "derived_from",
                "{}",
            ),
        )
        cursor.execute(
            """
            INSERT INTO graph.rendered_page (
                domain,
                layer,
                record_id,
                path,
                scope,
                tenant_id,
                user_id,
                fact_snapshot_id,
                metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                "recruiting",
                "personal",
                "personal:plan-1",
                "wiki/personal/tenant-1/user-1/plan-1.md",
                "user",
                "tenant-1",
                "user-1",
                "fact_snap:1",
                "{}",
            ),
        )
        cursor.execute(
            """
            INSERT INTO graph.rendered_page (
                domain,
                layer,
                record_id,
                path,
                scope,
                tenant_id,
                user_id,
                fact_snapshot_id,
                metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                "recruiting",
                "personal",
                "personal:plan-1",
                "wiki/personal/tenant-1/user-2/plan-1.md",
                "user",
                "tenant-1",
                "user-2",
                "fact_snap:1",
                "{}",
            ),
        )
    postgres_connection.commit()

    impact = repository.get_impact(
        "recruiting",
        "fact",
        "fact:job_posting:emp-1",
        {
            "scope": "user",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
        },
    )

    assert impact == {
        "affected_interpretation_ids": [],
        "affected_rendered_paths": ["wiki/personal/tenant-1/user-1/plan-1.md"],
        "affected_personal_ids": ["personal:plan-1"],
    }


def test_outbox_repository_requeues_retryable_failures(
    postgres_connection: Connection[dict],
) -> None:
    repository = PostgresOutboxRepository(postgres_connection)
    [event_id] = repository.append_events(
        [
            {
                "event_type": "fact_ingested",
                "aggregate_layer": "fact",
                "aggregate_id": "fact_snap:retry-1",
                "payload": {"fact_snapshot_id": "fact_snap:retry-1"},
            }
        ]
    )

    repository.claim_pending(limit=1, event_types=["fact_ingested"])
    repository.mark_failed(event_id, "temporary outage")

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT status, attempt_count, last_error, claimed_at IS NULL AS unclaimed,
                   available_at > NOW() AS delayed
            FROM ops.outbox_event
            WHERE id = %s
            """,
            (event_id,),
        )
        row = cursor.fetchone()

    assert row == {
        "status": "pending",
        "attempt_count": 1,
        "last_error": "temporary outage",
        "unclaimed": True,
        "delayed": True,
    }


def test_outbox_repository_terminally_fails_non_retryable_or_exhausted_events(
    postgres_connection: Connection[dict],
) -> None:
    repository = PostgresOutboxRepository(postgres_connection)
    [event_id] = repository.append_events(
        [
            {
                "event_type": "fact_ingested",
                "aggregate_layer": "fact",
                "aggregate_id": "fact_snap:retry-2",
                "payload": {"fact_snapshot_id": "fact_snap:retry-2"},
            }
        ]
    )

    repository.claim_pending(limit=1, event_types=["fact_ingested"])
    repository.mark_failed(event_id, "bad payload", retryable=False)

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, last_error FROM ops.outbox_event WHERE id = %s",
            (event_id,),
        )
        non_retryable_row = cursor.fetchone()
        cursor.execute(
            """
            UPDATE ops.outbox_event
            SET status = 'claimed', attempt_count = 3, claimed_at = NOW()
            WHERE id = %s
            """,
            (event_id,),
        )
    postgres_connection.commit()

    repository.mark_failed(event_id, "still broken")

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, attempt_count, last_error FROM ops.outbox_event WHERE id = %s",
            (event_id,),
        )
        exhausted_row = cursor.fetchone()

    assert non_retryable_row == {"status": "failed", "last_error": "bad payload"}
    assert exhausted_row == {
        "status": "failed",
        "attempt_count": 3,
        "last_error": "still broken",
    }
