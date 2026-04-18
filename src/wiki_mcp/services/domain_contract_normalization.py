from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wiki_mcp.schemas.domain_pack import DomainPack
from wiki_mcp.schemas.domain_proposal import DomainProposalBatch


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return list(value)


def _first(raw: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def _string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _copy_unknown_fields(
    target: dict[str, Any],
    raw: Mapping[str, Any],
    *,
    known_keys: set[str],
) -> None:
    for key, value in raw.items():
        if key not in known_keys:
            target[key] = value


def normalize_domain_pack(pack: Any) -> DomainPack:
    raw = _mapping(pack)
    manifest = _normalize_manifest(_mapping(_first(raw, "manifest")))
    entity_types = _normalize_entity_types(_mapping(_first(raw, "entity_types", "entityTypes")))
    relation_types = _normalize_relation_types(
        _mapping(_first(raw, "relation_types", "relationTypes"))
    )

    normalized: DomainPack = {
        "manifest": manifest,
        "entity_types": entity_types,
        "relation_types": relation_types,
    }

    projection_hints = _normalize_projection_hints(
        _mapping(_first(raw, "projection_hints", "projectionHints"))
    )
    if projection_hints:
        normalized["projection_hints"] = projection_hints

    proposal_surface = _normalize_proposal_surface(
        _mapping(_first(raw, "proposal_surface", "proposalSurface"))
    )
    if proposal_surface:
        normalized["proposal_surface"] = proposal_surface

    _copy_unknown_fields(
        normalized,
        raw,
        known_keys={
            "manifest",
            "entity_types",
            "entityTypes",
            "relation_types",
            "relationTypes",
            "projection_hints",
            "projectionHints",
            "proposal_surface",
            "proposalSurface",
        },
    )

    return normalized


def normalize_domain_proposal_batch(batch: Any) -> DomainProposalBatch:
    raw = _mapping(batch)
    normalized: DomainProposalBatch = {}

    batch_id = _string(_first(raw, "batch_id", "batchId"))
    if batch_id is not None:
        normalized["batch_id"] = batch_id

    domain = _string(_first(raw, "domain"))
    if domain is not None:
        normalized["domain"] = domain

    pack_version = _string(_first(raw, "pack_version", "packVersion"))
    if pack_version is not None:
        normalized["pack_version"] = pack_version

    producer = _string(_first(raw, "producer"))
    if producer is not None:
        normalized["producer"] = producer

    scope_ref = _mapping(_first(raw, "scope_ref", "scopeRef"))
    if scope_ref:
        normalized["scope_ref"] = scope_ref

    submitted_at = _string(_first(raw, "submitted_at", "submittedAt"))
    if submitted_at is not None:
        normalized["submitted_at"] = submitted_at

    metadata = _mapping(_first(raw, "metadata"))
    if metadata:
        normalized["metadata"] = metadata

    facts = [
        _normalize_fact_proposal(item)
        for item in _list(_first(raw, "facts"))
        if isinstance(item, Mapping)
    ]
    if facts:
        normalized["facts"] = facts

    relations = [
        _normalize_relation_proposal(item)
        for item in _list(_first(raw, "relations"))
        if isinstance(item, Mapping)
    ]
    if relations:
        normalized["relations"] = relations

    return normalized


def _normalize_manifest(raw: Mapping[str, Any]) -> dict[str, Any]:
    compatibility_raw = _mapping(_first(raw, "compatibility"))
    owner_raw = _mapping(_first(raw, "owner"))

    compatibility: dict[str, Any] = {}
    min_version = _string(
        _first(
            compatibility_raw,
            "min_stratawiki_version",
            "minStrataWikiVersion",
        )
    )
    if min_version is not None:
        compatibility["min_stratawiki_version"] = min_version

    max_version = _string(
        _first(
            compatibility_raw,
            "max_stratawiki_version",
            "maxStrataWikiVersion",
        )
    )
    if max_version is not None:
        compatibility["max_stratawiki_version"] = max_version

    owner: dict[str, Any] = {}
    system = _string(_first(owner_raw, "system"))
    if system is not None:
        owner["system"] = system
    team = _string(_first(owner_raw, "team"))
    if team is not None:
        owner["team"] = team

    manifest: dict[str, Any] = {
        "domain": _string(_first(raw, "domain")) or "",
        "pack_version": _string(_first(raw, "pack_version", "packVersion")) or "",
        "compatibility": compatibility,
        "owner": owner,
    }

    status = _string(_first(raw, "status"))
    if status is not None:
        manifest["status"] = status

    source_profiles = [
        item.strip()
        for item in _list(_first(raw, "source_profiles", "sourceProfiles"))
        if isinstance(item, str) and item.strip()
    ]
    if source_profiles:
        manifest["source_profiles"] = source_profiles

    _copy_unknown_fields(
        manifest,
        raw,
        known_keys={
            "domain",
            "pack_version",
            "packVersion",
            "compatibility",
            "owner",
            "status",
            "source_profiles",
            "sourceProfiles",
        },
    )

    return manifest


def _normalize_entity_types(raw: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, Mapping):
            continue
        definition = dict(value)
        entity: dict[str, Any] = {
            "name": _string(_first(definition, "name")) or key,
            "attributes": _normalize_attributes(_mapping(_first(definition, "attributes"))),
            "required_attributes": [
                item.strip()
                for item in _list(_first(definition, "required_attributes", "requiredAttributes"))
                if isinstance(item, str) and item.strip()
            ],
            "identity": _normalize_identity_rule(_mapping(_first(definition, "identity"))),
            "merge_policy": _normalize_merge_policy(
                _mapping(_first(definition, "merge_policy", "mergePolicy"))
            ),
        }
        description = _string(_first(definition, "description"))
        if description is not None:
            entity["description"] = description
        _copy_unknown_fields(
            entity,
            definition,
            known_keys={
                "name",
                "description",
                "attributes",
                "required_attributes",
                "requiredAttributes",
                "identity",
                "merge_policy",
                "mergePolicy",
            },
        )
        normalized[key] = entity
    return normalized


def _normalize_relation_types(raw: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, Mapping):
            continue
        definition = dict(value)
        relation: dict[str, Any] = {
            "name": _string(_first(definition, "name")) or key,
            "from_entity_types": [
                item.strip()
                for item in _list(_first(definition, "from_entity_types", "fromEntityTypes"))
                if isinstance(item, str) and item.strip()
            ],
            "to_entity_types": [
                item.strip()
                for item in _list(_first(definition, "to_entity_types", "toEntityTypes"))
                if isinstance(item, str) and item.strip()
            ],
        }
        description = _string(_first(definition, "description"))
        if description is not None:
            relation["description"] = description
        attributes = _normalize_attributes(_mapping(_first(definition, "attributes")))
        if attributes:
            relation["attributes"] = attributes
        cardinality = _string(_first(definition, "cardinality"))
        if cardinality is not None:
            relation["cardinality"] = cardinality
        evidence_policy = _string(
            _first(definition, "evidence_policy", "evidencePolicy")
        )
        if evidence_policy is not None:
            relation["evidence_policy"] = evidence_policy
        _copy_unknown_fields(
            relation,
            definition,
            known_keys={
                "name",
                "description",
                "from_entity_types",
                "fromEntityTypes",
                "to_entity_types",
                "toEntityTypes",
                "attributes",
                "cardinality",
                "evidence_policy",
                "evidencePolicy",
            },
        )
        normalized[key] = relation
    return normalized


def _normalize_attributes(raw: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, Mapping):
            continue
        definition = dict(value)
        attribute: dict[str, Any] = {}
        attr_type = _string(_first(definition, "type"))
        if attr_type is not None:
            attribute["type"] = attr_type
        description = _string(_first(definition, "description"))
        if description is not None:
            attribute["description"] = description
        enum = [
            item
            for item in _list(_first(definition, "enum"))
            if isinstance(item, str) and item.strip()
        ]
        if enum:
            attribute["enum"] = enum
        if isinstance(_first(definition, "nullable"), bool):
            attribute["nullable"] = bool(definition["nullable"])
        _copy_unknown_fields(
            attribute,
            definition,
            known_keys={"type", "description", "enum", "nullable"},
        )
        normalized[key] = attribute
    return normalized


def _normalize_identity_rule(raw: Mapping[str, Any]) -> dict[str, Any]:
    mode = _string(_first(raw, "mode")) or ""
    if mode == "external_id":
        identity: dict[str, Any] = {
            "mode": mode,
            "field": _string(_first(raw, "field")) or "",
        }
        prefix = _string(_first(raw, "prefix"))
        if prefix is not None:
            identity["prefix"] = prefix
        _copy_unknown_fields(identity, raw, known_keys={"mode", "field", "prefix"})
        return identity

    if mode == "composite":
        identity = {
            "mode": mode,
            "fields": [
                item.strip()
                for item in _list(_first(raw, "fields"))
                if isinstance(item, str) and item.strip()
            ],
            "prefix": _string(_first(raw, "prefix")) or "",
        }
        normalization = _normalize_normalization_rules(_list(_first(raw, "normalization")))
        if normalization:
            identity["normalization"] = normalization
        _copy_unknown_fields(
            identity,
            raw,
            known_keys={"mode", "fields", "prefix", "normalization"},
        )
        return identity

    if mode == "hint_priority":
        strategies: list[dict[str, Any]] = []
        for item in _list(_first(raw, "strategies")):
            if not isinstance(item, Mapping):
                continue
            strategy_raw = dict(item)
            strategy: dict[str, Any] = {
                "hint": _string(_first(strategy_raw, "hint")) or "",
            }
            prefix = _string(_first(strategy_raw, "prefix"))
            if prefix is not None:
                strategy["prefix"] = prefix
            normalization = _normalize_normalization_rules(
                _list(_first(strategy_raw, "normalization"))
            )
            if normalization:
                strategy["normalization"] = normalization
            description = _string(_first(strategy_raw, "description"))
            if description is not None:
                strategy["description"] = description
            _copy_unknown_fields(
                strategy,
                strategy_raw,
                known_keys={"hint", "prefix", "normalization", "description"},
            )
            strategies.append(strategy)
        identity = {
            "mode": mode,
            "strategies": strategies,
            "fallback": _string(_first(raw, "fallback")) or "reject",
        }
        _copy_unknown_fields(
            identity,
            raw,
            known_keys={"mode", "strategies", "fallback"},
        )
        return identity

    identity = {"mode": mode}
    _copy_unknown_fields(identity, raw, known_keys={"mode"})
    return identity


def _normalize_merge_policy(raw: Mapping[str, Any]) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "mode": _string(_first(raw, "mode")) or "",
        "conflict_strategy": _string(
            _first(raw, "conflict_strategy", "conflictStrategy")
        )
        or "",
    }
    source_timestamp_attribute = _string(
        _first(raw, "source_timestamp_attribute", "sourceTimestampAttribute")
    )
    if source_timestamp_attribute is not None:
        policy["source_timestamp_attribute"] = source_timestamp_attribute
    _copy_unknown_fields(
        policy,
        raw,
        known_keys={
            "mode",
            "conflict_strategy",
            "conflictStrategy",
            "source_timestamp_attribute",
            "sourceTimestampAttribute",
        },
    )
    return policy


def _normalize_projection_hints(raw: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    default_title_attribute = _normalize_string_mapping(
        _mapping(_first(raw, "default_title_attribute", "defaultTitleAttribute"))
    )
    if default_title_attribute:
        normalized["default_title_attribute"] = default_title_attribute

    searchable_attributes = _normalize_string_list_mapping(
        _mapping(_first(raw, "searchable_attributes", "searchableAttributes"))
    )
    if searchable_attributes:
        normalized["searchable_attributes"] = searchable_attributes

    default_families = [
        item.strip()
        for item in _list(_first(raw, "default_families", "defaultFamilies"))
        if isinstance(item, str) and item.strip()
    ]
    if default_families:
        normalized["default_families"] = default_families

    summary_attributes = _normalize_string_list_mapping(
        _mapping(_first(raw, "summary_attributes", "summaryAttributes"))
    )
    if summary_attributes:
        normalized["summary_attributes"] = summary_attributes

    temporal_attributes: dict[str, dict[str, str]] = {}
    for key, value in _mapping(
        _first(raw, "temporal_attributes", "temporalAttributes")
    ).items():
        if not isinstance(key, str) or not isinstance(value, Mapping):
            continue
        temporal: dict[str, str] = {}
        start = _string(_first(value, "start"))
        if start is not None:
            temporal["start"] = start
        end = _string(_first(value, "end"))
        if end is not None:
            temporal["end"] = end
        if temporal:
            temporal_attributes[key] = temporal
    if temporal_attributes:
        normalized["temporal_attributes"] = temporal_attributes

    default_family_by_entity_type = _normalize_string_mapping(
        _mapping(
            _first(
                raw,
                "default_family_by_entity_type",
                "defaultFamilyByEntityType",
            )
        )
    )
    if default_family_by_entity_type:
        normalized["default_family_by_entity_type"] = default_family_by_entity_type

    _copy_unknown_fields(
        normalized,
        raw,
        known_keys={
            "default_title_attribute",
            "defaultTitleAttribute",
            "searchable_attributes",
            "searchableAttributes",
            "default_families",
            "defaultFamilies",
            "summary_attributes",
            "summaryAttributes",
            "temporal_attributes",
            "temporalAttributes",
            "default_family_by_entity_type",
            "defaultFamilyByEntityType",
        },
    )

    return normalized


def _normalize_proposal_surface(raw: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    accepts_raw = _mapping(_first(raw, "accepts"))
    accepts: dict[str, bool] = {}
    for field, alternate in (
        ("fact_proposal", "factProposal"),
        ("relation_proposal", "relationProposal"),
    ):
        value = _first(accepts_raw, field, alternate)
        if isinstance(value, bool):
            accepts[field] = value
    if accepts:
        normalized["accepts"] = accepts

    strict_unknown_attributes = _first(
        raw,
        "strict_unknown_attributes",
        "strictUnknownAttributes",
    )
    if isinstance(strict_unknown_attributes, bool):
        normalized["strict_unknown_attributes"] = strict_unknown_attributes

    batch_mode = _string(_first(raw, "batch_mode", "batchMode"))
    if batch_mode is not None:
        normalized["batch_mode"] = batch_mode

    _copy_unknown_fields(
        normalized,
        raw,
        known_keys={
            "accepts",
            "strict_unknown_attributes",
            "strictUnknownAttributes",
            "batch_mode",
            "batchMode",
        },
    )

    return normalized


def _normalize_fact_proposal(raw_item: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(raw_item)
    proposal: dict[str, Any] = {
        "proposal_id": _string(_first(raw, "proposal_id", "proposalId")) or "",
        "domain": _string(_first(raw, "domain")) or "",
        "entity_type": _string(_first(raw, "entity_type", "entityType")) or "",
        "attributes": dict(_mapping(_first(raw, "attributes"))),
    }
    identity_hints = _normalize_string_mapping(
        _mapping(_first(raw, "identity_hints", "identityHints"))
    )
    if identity_hints:
        proposal["identity_hints"] = identity_hints
    evidence = _normalize_evidence(_list(_first(raw, "evidence")))
    if evidence:
        proposal["evidence"] = evidence
    return proposal


def _normalize_relation_proposal(raw_item: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(raw_item)
    proposal: dict[str, Any] = {
        "proposal_id": _string(_first(raw, "proposal_id", "proposalId")) or "",
        "domain": _string(_first(raw, "domain")) or "",
        "relation_type": _string(_first(raw, "relation_type", "relationType")) or "",
    }

    from_ref = _normalize_entity_ref(_mapping(_first(raw, "from_ref", "fromRef")))
    if from_ref:
        proposal["from_ref"] = from_ref
    to_ref = _normalize_entity_ref(_mapping(_first(raw, "to_ref", "toRef")))
    if to_ref:
        proposal["to_ref"] = to_ref

    attributes = _mapping(_first(raw, "attributes"))
    if attributes:
        proposal["attributes"] = dict(attributes)
    evidence = _normalize_evidence(_list(_first(raw, "evidence")))
    if evidence:
        proposal["evidence"] = evidence
    return proposal


def _normalize_entity_ref(raw: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    proposal_id = _string(_first(raw, "proposal_id", "proposalId"))
    if proposal_id is not None:
        normalized["proposal_id"] = proposal_id
    entity_type = _string(_first(raw, "entity_type", "entityType"))
    if entity_type is not None:
        normalized["entity_type"] = entity_type
    attributes = _mapping(_first(raw, "attributes"))
    if attributes:
        normalized["attributes"] = dict(attributes)
    identity_hints = _normalize_string_mapping(
        _mapping(_first(raw, "identity_hints", "identityHints"))
    )
    if identity_hints:
        normalized["identity_hints"] = identity_hints
    return normalized


def _normalize_evidence(items: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        connector = _string(_first(item, "connector"))
        source_id = _string(_first(item, "source_id", "sourceId"))
        if connector is None or source_id is None:
            continue
        evidence: dict[str, str] = {
            "connector": connector,
            "source_id": source_id,
        }
        pointer = _string(_first(item, "pointer"))
        if pointer is not None:
            evidence["pointer"] = pointer
        normalized.append(evidence)
    return normalized


def _normalize_normalization_rules(items: list[Any]) -> list[str]:
    return [item.strip() for item in items if isinstance(item, str) and item.strip()]


def _normalize_string_mapping(raw: Mapping[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in raw.items():
        normalized_key = _string(key)
        normalized_value = _string(value)
        if normalized_key is None or normalized_value is None:
            continue
        normalized[normalized_key] = normalized_value
    return normalized


def _normalize_string_list_mapping(raw: Mapping[str, Any]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, value in raw.items():
        normalized_key = _string(key)
        if normalized_key is None or not isinstance(value, list):
            continue
        normalized_values = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if normalized_values:
            normalized[normalized_key] = normalized_values
    return normalized
