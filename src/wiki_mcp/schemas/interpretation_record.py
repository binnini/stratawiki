from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NotRequired, TypedDict

from wiki_mcp.schemas.interpretation_lifecycle import InterpretationLifecycleStatus
from wiki_mcp.schemas.provenance import Provenance
from wiki_mcp.schemas.scope_ref import ScopeRef


class InterpretationRecord(TypedDict):
    """Canonical shared Interpretation record envelope."""

    id: str
    layer: NotRequired[str]
    domain: str
    family: NotRequired[str]
    kind: str
    subject_type: str
    subject_id: str
    subject_label: NotRequired[str]
    subject: NotRequired[dict[str, str]]
    scope_ref: ScopeRef
    schema_version: str
    status: InterpretationLifecycleStatus
    confidence: float
    fact_snapshot_id: str
    computed_at: str
    expires_at: str | None
    interpretation_snapshot_id: NotRequired[str]
    created_at: NotRequired[str]
    updated_at: NotRequired[str]
    version: NotRequired[int]
    title: NotRequired[str]
    claim: NotRequired[str]
    summary: NotRequired[str]
    payload: NotRequired[dict[str, Any]]
    body: dict[str, Any]
    evidence: NotRequired[list[dict[str, Any]]]
    relations: NotRequired[list[dict[str, Any]]]
    support_links: NotRequired[list[dict[str, Any]]]
    freshness: NotRequired[dict[str, Any]]
    confidence_detail: NotRequired[dict[str, float]]
    provenance: Provenance
    render_hints: dict[str, Any]


def interpretation_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical payload view for one interpretation record."""

    payload: dict[str, Any] = {}
    raw_payload = record.get("payload")
    if isinstance(raw_payload, Mapping):
        payload.update(dict(raw_payload))

    for key in ("title", "claim", "summary"):
        value = record.get(key)
        if key not in payload and isinstance(value, str) and value.strip():
            payload[key] = value.strip()

    body = payload.get("body")
    if not isinstance(body, dict):
        raw_body = record.get("body")
        body = dict(raw_body) if isinstance(raw_body, Mapping) else {}
        payload["body"] = body
    else:
        payload["body"] = dict(body)

    for key in ("freshness", "confidence_detail"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            payload[key] = dict(value)
            continue
        record_value = record.get(key)
        if isinstance(record_value, Mapping):
            payload[key] = dict(record_value)

    return payload


def interpretation_support_links(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return canonical support links, projecting legacy evidence/relations when needed."""

    raw_links = record.get("support_links")
    if isinstance(raw_links, list):
        normalized = [_normalize_support_link(item) for item in raw_links]
        return [item for item in normalized if item is not None]

    support_links: list[dict[str, Any]] = []
    raw_evidence = record.get("evidence")
    if isinstance(raw_evidence, list):
        for item in raw_evidence:
            if not isinstance(item, Mapping):
                continue
            fact_id = item.get("fact_id")
            if not isinstance(fact_id, str) or not fact_id.strip():
                continue
            attributes = {
                key: value
                for key, value in dict(item).items()
                if key not in {"fact_id", "role", "weight"}
            }
            support_links.append(
                {
                    "link_kind": "fact_support",
                    "target_layer": "fact",
                    "target_id": fact_id.strip(),
                    **({"role": item["role"]} if isinstance(item.get("role"), str) else {}),
                    **(
                        {"weight": float(item["weight"])}
                        if isinstance(item.get("weight"), (int, float))
                        else {}
                    ),
                    "support_ref": {"fact_id": fact_id.strip()},
                    **({"attributes": attributes} if attributes else {}),
                }
            )

    raw_relations = record.get("relations")
    if isinstance(raw_relations, list):
        for item in raw_relations:
            if not isinstance(item, Mapping):
                continue
            support_ref = dict(item)
            target_id = item.get("relation_id")
            support_links.append(
                {
                    "link_kind": "relation_support",
                    "target_layer": "relation",
                    **({"target_id": target_id.strip()} if isinstance(target_id, str) and target_id.strip() else {}),
                    "support_ref": support_ref,
                }
            )
    return support_links


def materialize_interpretation_record(record: Mapping[str, Any]) -> InterpretationRecord:
    """Return one record with both canonical and legacy-compatible projections attached."""

    materialized = dict(record)
    payload = interpretation_payload(materialized)
    materialized["payload"] = payload

    title = payload.get("title")
    if isinstance(title, str) and title.strip():
        materialized["title"] = title.strip()
    claim = payload.get("claim")
    if isinstance(claim, str) and claim.strip():
        materialized["claim"] = claim.strip()
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        materialized["summary"] = summary.strip()
    body = payload.get("body")
    materialized["body"] = dict(body) if isinstance(body, Mapping) else {}

    for key in ("freshness", "confidence_detail"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            materialized[key] = dict(value)

    support_links = interpretation_support_links(materialized)
    materialized["support_links"] = support_links

    if "evidence" not in materialized:
        legacy_evidence: list[dict[str, Any]] = []
        for item in support_links:
            if item.get("target_layer") != "fact":
                continue
            target_id = item.get("target_id")
            if not isinstance(target_id, str) or not target_id.strip():
                support_ref = item.get("support_ref")
                if isinstance(support_ref, Mapping):
                    raw_fact_id = support_ref.get("fact_id")
                    if isinstance(raw_fact_id, str) and raw_fact_id.strip():
                        target_id = raw_fact_id.strip()
            if not isinstance(target_id, str) or not target_id.strip():
                continue
            legacy_evidence.append(
                {
                    "fact_id": target_id,
                    **({"role": item["role"]} if isinstance(item.get("role"), str) else {}),
                    **(
                        {"weight": float(item["weight"])}
                        if isinstance(item.get("weight"), (int, float))
                        else {}
                    ),
                }
            )
        materialized["evidence"] = legacy_evidence

    if "relations" not in materialized:
        legacy_relations: list[dict[str, Any]] = []
        for item in support_links:
            if item.get("target_layer") != "relation":
                continue
            support_ref = item.get("support_ref")
            if isinstance(support_ref, Mapping):
                legacy_relations.append(dict(support_ref))
        materialized["relations"] = legacy_relations

    return materialized  # type: ignore[return-value]


def _normalize_support_link(item: object) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None

    normalized: dict[str, Any] = {}
    for key in ("link_kind", "target_layer", "target_id", "role"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()

    weight = item.get("weight")
    if isinstance(weight, (int, float)):
        normalized["weight"] = float(weight)

    support_ref = item.get("support_ref")
    if isinstance(support_ref, Mapping):
        normalized["support_ref"] = dict(support_ref)

    attributes = item.get("attributes")
    if isinstance(attributes, Mapping):
        normalized["attributes"] = dict(attributes)

    if not normalized.get("target_layer"):
        if isinstance(normalized.get("support_ref"), Mapping) and normalized["support_ref"].get("fact_id"):
            normalized["target_layer"] = "fact"
        elif "relation" in str(normalized.get("link_kind") or ""):
            normalized["target_layer"] = "relation"

    if not normalized.get("link_kind"):
        normalized["link_kind"] = (
            "relation_support"
            if normalized.get("target_layer") == "relation"
            else "fact_support"
        )

    if not normalized.get("target_layer"):
        return None
    return normalized
