from __future__ import annotations

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.services.interpretation_families.base import InterpretationBuildContext


def company_name(*, company: FactRecord | None, posting: FactRecord) -> object:
    return (
        (company["attributes"].get("name") if company else None)
        or posting["attributes"].get("company_name")
        or "unknown"
    )


def subject_id(*, company: FactRecord | None, posting: FactRecord) -> str:
    return company["canonical_key"] if company else posting["canonical_key"]


def require_posting(facts: list[FactRecord], family: str) -> FactRecord:
    posting = next((fact for fact in facts if fact["entity_type"] == "job_posting"), None)
    if posting is None:
        raise ValueError(
            f"{family} projection requires a job_posting fact in the affected batch."
        )
    return posting


def provenance(context: InterpretationBuildContext) -> dict[str, object]:
    return {
        "source_event_id": context.source_event_id,
        "fact_snapshot_id": context.payload["fact_snapshot_id"],
        "source_id": context.payload["source_id"],
        "connector": context.payload["connector"],
        "evidence_fact_ids": [fact["id"] for fact in context.facts],
    }


def rendered_artifact(
    *,
    record: InterpretationRecord,
    title: str,
    body_markdown: str,
    snapshot_ref: SnapshotRef,
) -> dict[str, object]:
    return {
        "domain": record["domain"],
        "layer": "interpretation",
        "record_id": record["id"],
        "path": rendered_path_for_record(record),
        "title": title,
        "body_markdown": body_markdown,
        "scope_ref": record["scope_ref"],
        "snapshot_ref": snapshot_ref,
    }


def rendered_path_for_record(record: InterpretationRecord) -> str:
    subject_key = record["subject_id"].replace(":", "__")
    return f"wiki/shared/{record['domain']}/{record['kind']}/{subject_key}.md"


def snapshot_lines(snapshot_ref: SnapshotRef) -> list[str]:
    return [
        "",
        "## Snapshot Provenance",
        f"- fact_snapshot_id: {snapshot_ref['fact_snapshot_id']}",
        f"- interpretation_snapshot_id: {snapshot_ref.get('interpretation_snapshot_id', '')}",
    ]
