from __future__ import annotations

from wiki_mcp.services.interpretation_family_builders import (
    InterpretationBuildContext,
    InterpretationFamilyRegistry,
)


class StubBuilder:
    def __init__(
        self,
        family: str,
        *,
        record: dict[str, object] | None,
        artifact_title: str | None = None,
    ) -> None:
        self.family = family
        self.record = record
        self.artifact_title = artifact_title or family

    def build_record(
        self,
        context: InterpretationBuildContext,
    ) -> dict[str, object] | None:
        return self.record

    def build_rendered_artifact(
        self,
        record: dict[str, object],
        *,
        snapshot_ref: dict[str, str],
    ) -> dict[str, object]:
        return {
            "record_id": record["id"],
            "title": self.artifact_title,
            "snapshot_ref": snapshot_ref,
        }


def test_registry_collects_only_records_built_by_enabled_families() -> None:
    registry = InterpretationFamilyRegistry(
        [
            StubBuilder(
                "family_a",
                record={"id": "interp:family_a:1", "kind": "family_a"},
            ),
            StubBuilder("family_b", record=None),
            StubBuilder(
                "family_c",
                record={"id": "interp:family_c:1", "kind": "family_c"},
            ),
        ]
    )

    records = registry.build_records(
        InterpretationBuildContext(
            payload={
                "domain": "recruiting",
                "source_id": "EMP-1",
                "connector": "worknet",
                "fact_snapshot_id": "fact_snap:1",
                "affected_fact_ids": [],
                "affected_entity_types": [],
                "scope": "shared",
                "facts_created": 0,
                "facts_updated": 0,
                "relations_created": 0,
            },
            facts=[],
            scope_ref={"scope": "shared"},
            source_event_id="evt-1",
            schema_version="v1",
        )
    )

    assert [record["kind"] for record in records] == ["family_a", "family_c"]


def test_registry_routes_rendered_artifact_to_builder_for_record_kind() -> None:
    registry = InterpretationFamilyRegistry(
        [
            StubBuilder("family_a", record=None),
            StubBuilder("family_b", record=None, artifact_title="family b artifact"),
        ]
    )

    artifact = registry.build_rendered_artifact(
        {"id": "interp:family_b:1", "kind": "family_b"},
        snapshot_ref={
            "fact_snapshot_id": "fact_snap:1",
            "interpretation_snapshot_id": "interp_snap:1",
        },
    )

    assert artifact["record_id"] == "interp:family_b:1"
    assert artifact["title"] == "family b artifact"


def test_registry_rejects_rendering_for_unknown_family() -> None:
    registry = InterpretationFamilyRegistry([StubBuilder("family_a", record=None)])

    try:
        registry.build_rendered_artifact(
            {"id": "interp:family_b:1", "kind": "family_b"},
            snapshot_ref={"fact_snapshot_id": "fact_snap:1"},
        )
    except ValueError as exc:
        assert "family_b" in str(exc)
    else:
        raise AssertionError("Expected ValueError for an unknown interpretation family")
