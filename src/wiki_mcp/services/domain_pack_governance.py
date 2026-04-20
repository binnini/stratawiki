from __future__ import annotations

from datetime import UTC, datetime

from collections.abc import Mapping
from typing import Any

from wiki_mcp.schemas.domain_pack import DomainPack
from wiki_mcp.schemas.domain_pack_review import (
    DomainPackApprovalReport,
    DomainPackApprovalAuditRecord,
    DomainPackCompatibilityDecision,
    DomainPackCompatibilityIssue,
    DomainPackCompatibilityReport,
    DomainPackRegistrationError,
    DomainPackReviewAudit,
    DomainPackValidationIssue,
    DomainPackValidationReport,
)
from wiki_mcp.services.domain_contract_normalization import normalize_domain_pack
from wiki_mcp.services.domain_pack_registry import DomainPackRegistryError
from wiki_mcp.services.interfaces.domain_pack_governance import (
    DomainPackApprovalService,
    DomainPackCompatibilityChecker,
    DomainPackReviewAuditRepository,
    DomainPackValidator,
)
from wiki_mcp.services.interfaces.domain_pack_registry import DomainPackRegistry

_TOP_LEVEL_KEYS = {
    "manifest",
    "entity_types",
    "relation_types",
    "projection_hints",
    "proposal_surface",
}
_MANIFEST_KEYS = {"domain", "pack_version", "compatibility", "owner", "status", "source_profiles"}
_COMPATIBILITY_KEYS = {"min_stratawiki_version", "max_stratawiki_version"}
_OWNER_KEYS = {"system", "team"}
_ENTITY_KEYS = {"name", "description", "attributes", "required_attributes", "identity", "merge_policy"}
_RELATION_KEYS = {
    "name",
    "description",
    "from_entity_types",
    "to_entity_types",
    "attributes",
    "cardinality",
    "evidence_policy",
}
_ATTRIBUTE_KEYS = {"type", "description", "enum", "nullable"}
_EXTERNAL_IDENTITY_KEYS = {"mode", "field", "prefix"}
_COMPOSITE_IDENTITY_KEYS = {"mode", "fields", "prefix", "normalization"}
_HINT_PRIORITY_IDENTITY_KEYS = {"mode", "strategies", "fallback"}
_HINT_PRIORITY_STRATEGY_KEYS = {"hint", "prefix", "normalization", "description"}
_MERGE_POLICY_KEYS = {"mode", "conflict_strategy", "source_timestamp_attribute"}
_PROJECTION_HINT_KEYS = {
    "default_title_attribute",
    "searchable_attributes",
    "default_families",
    "summary_attributes",
    "temporal_attributes",
    "default_family_by_entity_type",
}
_PROPOSAL_SURFACE_KEYS = {"accepts", "strict_unknown_attributes", "batch_mode"}
_PROPOSAL_SURFACE_ACCEPTS_KEYS = {"fact_proposal", "relation_proposal"}

_ATTRIBUTE_TYPES = {"string", "markdown", "datetime", "url", "integer", "number", "boolean", "json"}
_IDENTITY_MODES = {"external_id", "composite", "hint_priority"}
_IDENTITY_NORMALIZATION_RULES = {
    "trim",
    "lowercase",
    "slugify",
    "digits_only",
    "collapse_whitespace",
}
_IDENTITY_FALLBACKS = {"reject", "manual_review"}
_MERGE_MODES = {"upsert", "append_only"}
_MERGE_CONFLICT_STRATEGIES = {"prefer_newer_source", "prefer_existing", "manual_review"}
_RELATION_CARDINALITIES = {"one_to_one", "one_to_many", "many_to_many"}
_EVIDENCE_POLICIES = {"required", "optional"}
_RESERVED_IDENTITY_FIELDS = {"source_id", "external_id"}
_CARDINALITY_ORDER = {"one_to_one": 0, "one_to_many": 1, "many_to_many": 2}


class DefaultDomainPackValidator(DomainPackValidator):
    """Validate one Domain Pack artifact before registration or activation."""

    def validate(
        self,
        pack: DomainPack,
    ) -> DomainPackValidationReport:
        issues: list[DomainPackValidationIssue] = []

        if not isinstance(pack, Mapping):
            issues.append(
                self._issue(
                    code="invalid_shape",
                    path="$",
                    message="DomainPack must be a mapping.",
                )
            )
            return self._report(issues)

        pack_data = dict(normalize_domain_pack(pack))
        self._check_unknown_keys(pack_data, _TOP_LEVEL_KEYS, "$", issues)
        self._check_required_keys(
            pack_data,
            ("manifest", "entity_types", "relation_types"),
            "$",
            issues,
        )

        manifest = self._require_mapping(pack_data.get("manifest"), "manifest", issues)
        entity_types = self._require_mapping(pack_data.get("entity_types"), "entity_types", issues)
        relation_types = self._require_mapping(
            pack_data.get("relation_types"),
            "relation_types",
            issues,
        )
        projection_hints = pack_data.get("projection_hints")
        proposal_surface = pack_data.get("proposal_surface")

        entity_attribute_index: dict[str, set[str]] = {}
        if manifest is not None:
            self._validate_manifest(manifest, issues)
        if entity_types is not None:
            entity_attribute_index = self._validate_entity_types(entity_types, issues)
        if relation_types is not None:
            self._validate_relation_types(
                relation_types,
                known_entity_types=set(entity_attribute_index),
                issues=issues,
            )
        if projection_hints is not None:
            self._validate_projection_hints(
                projection_hints,
                entity_attribute_index=entity_attribute_index,
                issues=issues,
            )
        if proposal_surface is not None:
            self._validate_proposal_surface(proposal_surface, issues)

        return self._report(issues)

    def _validate_manifest(
        self,
        manifest: dict[str, Any],
        issues: list[DomainPackValidationIssue],
    ) -> None:
        self._check_unknown_keys(manifest, _MANIFEST_KEYS, "manifest", issues)
        self._check_required_keys(
            manifest,
            ("domain", "pack_version", "compatibility", "owner"),
            "manifest",
            issues,
        )
        self._require_non_empty_string(
            manifest.get("domain"),
            "manifest.domain",
            issues,
        )
        self._require_non_empty_string(
            manifest.get("pack_version"),
            "manifest.pack_version",
            issues,
        )
        compatibility = self._require_mapping(
            manifest.get("compatibility"),
            "manifest.compatibility",
            issues,
        )
        owner = self._require_mapping(
            manifest.get("owner"),
            "manifest.owner",
            issues,
        )

        if compatibility is not None:
            self._check_unknown_keys(
                compatibility,
                _COMPATIBILITY_KEYS,
                "manifest.compatibility",
                issues,
            )
            self._check_required_keys(
                compatibility,
                ("min_stratawiki_version",),
                "manifest.compatibility",
                issues,
            )
            self._require_non_empty_string(
                compatibility.get("min_stratawiki_version"),
                "manifest.compatibility.min_stratawiki_version",
                issues,
            )
            if "max_stratawiki_version" in compatibility:
                self._require_non_empty_string(
                    compatibility.get("max_stratawiki_version"),
                    "manifest.compatibility.max_stratawiki_version",
                    issues,
                )

        if owner is not None:
            self._check_unknown_keys(owner, _OWNER_KEYS, "manifest.owner", issues)
            self._check_required_keys(owner, ("system",), "manifest.owner", issues)
            self._require_non_empty_string(
                owner.get("system"),
                "manifest.owner.system",
                issues,
            )
            if "team" in owner:
                self._require_non_empty_string(
                    owner.get("team"),
                    "manifest.owner.team",
                    issues,
                )

        if "status" in manifest:
            status = manifest.get("status")
            if status not in {"draft", "approved", "active", "deprecated", "archived", "closed"}:
                issues.append(
                    self._issue(
                        code="invalid_manifest_status",
                        path="manifest.status",
                        message=(
                            "manifest.status must be one of "
                            "['active', 'approved', 'archived', 'closed', 'deprecated', 'draft']."
                        ),
                    )
                )

        if "source_profiles" in manifest:
            source_profiles = manifest.get("source_profiles")
            if not isinstance(source_profiles, list):
                issues.append(
                    self._issue(
                        code="invalid_source_profiles",
                        path="manifest.source_profiles",
                        message="manifest.source_profiles must be a list of non-empty strings.",
                    )
                )
            else:
                for index, profile in enumerate(source_profiles):
                    self._require_non_empty_string(
                        profile,
                        f"manifest.source_profiles[{index}]",
                        issues,
                    )

    def _validate_entity_types(
        self,
        entity_types: dict[str, Any],
        issues: list[DomainPackValidationIssue],
    ) -> dict[str, set[str]]:
        entity_attribute_index: dict[str, set[str]] = {}

        for entity_name, raw_definition in entity_types.items():
            path = f"entity_types.{entity_name}"
            if not isinstance(entity_name, str) or not entity_name.strip():
                issues.append(
                    self._issue(
                        code="invalid_entity_type_name",
                        path="entity_types",
                        message="Entity type keys must be non-empty strings.",
                    )
                )
                continue
            definition = self._require_mapping(raw_definition, path, issues)
            if definition is None:
                continue

            self._check_unknown_keys(definition, _ENTITY_KEYS, path, issues)
            self._check_required_keys(
                definition,
                ("name", "attributes", "required_attributes", "identity", "merge_policy"),
                path,
                issues,
            )
            self._require_name_matches_key(definition.get("name"), entity_name, f"{path}.name", issues)

            attributes = self._validate_attribute_definitions(
                definition.get("attributes"),
                f"{path}.attributes",
                issues,
            )
            entity_attribute_index[entity_name] = set(attributes)

            self._validate_required_attributes(
                definition.get("required_attributes"),
                available_attributes=set(attributes),
                path=f"{path}.required_attributes",
                issues=issues,
            )
            self._validate_identity_rule(
                definition.get("identity"),
                available_attributes=set(attributes),
                path=f"{path}.identity",
                issues=issues,
            )
            self._validate_merge_policy(
                definition.get("merge_policy"),
                attribute_definitions=attributes,
                path=f"{path}.merge_policy",
                issues=issues,
            )

            if "description" in definition and definition.get("description") is not None:
                self._require_non_empty_string(
                    definition.get("description"),
                    f"{path}.description",
                    issues,
                )

        return entity_attribute_index

    def _validate_relation_types(
        self,
        relation_types: dict[str, Any],
        *,
        known_entity_types: set[str],
        issues: list[DomainPackValidationIssue],
    ) -> None:
        for relation_name, raw_definition in relation_types.items():
            path = f"relation_types.{relation_name}"
            if not isinstance(relation_name, str) or not relation_name.strip():
                issues.append(
                    self._issue(
                        code="invalid_relation_type_name",
                        path="relation_types",
                        message="Relation type keys must be non-empty strings.",
                    )
                )
                continue
            definition = self._require_mapping(raw_definition, path, issues)
            if definition is None:
                continue

            self._check_unknown_keys(definition, _RELATION_KEYS, path, issues)
            self._check_required_keys(
                definition,
                ("name", "from_entity_types", "to_entity_types"),
                path,
                issues,
            )
            self._require_name_matches_key(definition.get("name"), relation_name, f"{path}.name", issues)
            self._validate_relation_endpoint_list(
                definition.get("from_entity_types"),
                known_entity_types=known_entity_types,
                path=f"{path}.from_entity_types",
                issues=issues,
            )
            self._validate_relation_endpoint_list(
                definition.get("to_entity_types"),
                known_entity_types=known_entity_types,
                path=f"{path}.to_entity_types",
                issues=issues,
            )

            if "attributes" in definition:
                self._validate_attribute_definitions(
                    definition.get("attributes"),
                    f"{path}.attributes",
                    issues,
                )
            if "cardinality" in definition and definition.get("cardinality") not in _RELATION_CARDINALITIES:
                issues.append(
                    self._issue(
                        code="invalid_relation_cardinality",
                        path=f"{path}.cardinality",
                        message=(
                            "Relation cardinality must be one of "
                            f"{sorted(_RELATION_CARDINALITIES)}, got {definition.get('cardinality')!r}."
                        ),
                    )
                )
            if "evidence_policy" in definition and definition.get("evidence_policy") not in _EVIDENCE_POLICIES:
                issues.append(
                    self._issue(
                        code="invalid_evidence_policy",
                        path=f"{path}.evidence_policy",
                        message=(
                            "Relation evidence_policy must be one of "
                            f"{sorted(_EVIDENCE_POLICIES)}, got {definition.get('evidence_policy')!r}."
                        ),
                    )
                )
            if "description" in definition and definition.get("description") is not None:
                self._require_non_empty_string(
                    definition.get("description"),
                    f"{path}.description",
                    issues,
                )

    def _validate_projection_hints(
        self,
        raw_projection_hints: Any,
        *,
        entity_attribute_index: dict[str, set[str]],
        issues: list[DomainPackValidationIssue],
    ) -> None:
        projection_hints = self._require_mapping(raw_projection_hints, "projection_hints", issues)
        if projection_hints is None:
            return

        self._check_unknown_keys(
            projection_hints,
            _PROJECTION_HINT_KEYS,
            "projection_hints",
            issues,
        )

        default_title_attribute = projection_hints.get("default_title_attribute")
        if default_title_attribute is not None:
            title_mapping = self._require_mapping(
                default_title_attribute,
                "projection_hints.default_title_attribute",
                issues,
            )
            if title_mapping is not None:
                for entity_name, attribute_name in title_mapping.items():
                    self._validate_projection_attribute_ref(
                        entity_name=entity_name,
                        attribute_name=attribute_name,
                        entity_attribute_index=entity_attribute_index,
                        path=f"projection_hints.default_title_attribute.{entity_name}",
                        issues=issues,
                    )

        searchable_attributes = projection_hints.get("searchable_attributes")
        if searchable_attributes is not None:
            searchable_mapping = self._require_mapping(
                searchable_attributes,
                "projection_hints.searchable_attributes",
                issues,
            )
            if searchable_mapping is not None:
                for entity_name, attribute_names in searchable_mapping.items():
                    path = f"projection_hints.searchable_attributes.{entity_name}"
                    if not isinstance(attribute_names, list) or not attribute_names:
                        issues.append(
                            self._issue(
                                code="invalid_projection_hint",
                                path=path,
                                message="searchable_attributes entries must be non-empty string lists.",
                            )
                        )
                        continue
                    for index, attribute_name in enumerate(attribute_names):
                        self._validate_projection_attribute_ref(
                            entity_name=entity_name,
                            attribute_name=attribute_name,
                            entity_attribute_index=entity_attribute_index,
                            path=f"{path}[{index}]",
                            issues=issues,
                        )

        default_families = projection_hints.get("default_families")
        if default_families is not None:
            if not isinstance(default_families, list):
                issues.append(
                    self._issue(
                        code="invalid_projection_hint",
                        path="projection_hints.default_families",
                        message="default_families must be a list of non-empty strings.",
                    )
                )
            else:
                for index, family in enumerate(default_families):
                    self._require_non_empty_string(
                        family,
                        f"projection_hints.default_families[{index}]",
                        issues,
                    )

        summary_attributes = projection_hints.get("summary_attributes")
        if summary_attributes is not None:
            summary_mapping = self._require_mapping(
                summary_attributes,
                "projection_hints.summary_attributes",
                issues,
            )
            if summary_mapping is not None:
                for entity_name, attribute_names in summary_mapping.items():
                    path = f"projection_hints.summary_attributes.{entity_name}"
                    if not isinstance(attribute_names, list):
                        issues.append(
                            self._issue(
                                code="invalid_projection_hint",
                                path=path,
                                message="summary_attributes entries must be string lists.",
                            )
                        )
                        continue
                    for index, attribute_name in enumerate(attribute_names):
                        self._validate_projection_attribute_ref(
                            entity_name=entity_name,
                            attribute_name=attribute_name,
                            entity_attribute_index=entity_attribute_index,
                            path=f"{path}[{index}]",
                            issues=issues,
                        )

        temporal_attributes = projection_hints.get("temporal_attributes")
        if temporal_attributes is not None:
            temporal_mapping = self._require_mapping(
                temporal_attributes,
                "projection_hints.temporal_attributes",
                issues,
            )
            if temporal_mapping is not None:
                for entity_name, window in temporal_mapping.items():
                    path = f"projection_hints.temporal_attributes.{entity_name}"
                    window_mapping = self._require_mapping(window, path, issues)
                    if window_mapping is None:
                        continue
                    self._check_unknown_keys(window_mapping, {"start", "end"}, path, issues)
                    if "start" in window_mapping:
                        self._validate_projection_attribute_ref(
                            entity_name=entity_name,
                            attribute_name=window_mapping.get("start"),
                            entity_attribute_index=entity_attribute_index,
                            path=f"{path}.start",
                            issues=issues,
                        )
                    if "end" in window_mapping:
                        self._validate_projection_attribute_ref(
                            entity_name=entity_name,
                            attribute_name=window_mapping.get("end"),
                            entity_attribute_index=entity_attribute_index,
                            path=f"{path}.end",
                            issues=issues,
                        )

        default_family_by_entity_type = projection_hints.get("default_family_by_entity_type")
        if default_family_by_entity_type is not None:
            family_mapping = self._require_mapping(
                default_family_by_entity_type,
                "projection_hints.default_family_by_entity_type",
                issues,
            )
            if family_mapping is not None:
                for entity_name, family in family_mapping.items():
                    if entity_name not in entity_attribute_index:
                        issues.append(
                            self._issue(
                                code="invalid_projection_hint",
                                path=f"projection_hints.default_family_by_entity_type.{entity_name}",
                                message=(
                                    f"default_family_by_entity_type references unknown entity_type "
                                    f"{entity_name!r}."
                                ),
                            )
                        )
                        continue
                    self._require_non_empty_string(
                        family,
                        f"projection_hints.default_family_by_entity_type.{entity_name}",
                        issues,
                    )

    def _validate_proposal_surface(
        self,
        raw_proposal_surface: Any,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        proposal_surface = self._require_mapping(raw_proposal_surface, "proposal_surface", issues)
        if proposal_surface is None:
            return

        self._check_unknown_keys(
            proposal_surface,
            _PROPOSAL_SURFACE_KEYS,
            "proposal_surface",
            issues,
        )

        accepts = proposal_surface.get("accepts")
        if accepts is not None:
            accepts_mapping = self._require_mapping(
                accepts,
                "proposal_surface.accepts",
                issues,
            )
            if accepts_mapping is not None:
                self._check_unknown_keys(
                    accepts_mapping,
                    _PROPOSAL_SURFACE_ACCEPTS_KEYS,
                    "proposal_surface.accepts",
                    issues,
                )
                for key in _PROPOSAL_SURFACE_ACCEPTS_KEYS:
                    if key in accepts_mapping and not isinstance(accepts_mapping.get(key), bool):
                        issues.append(
                            self._issue(
                                code="invalid_proposal_surface",
                                path=f"proposal_surface.accepts.{key}",
                                message="proposal_surface.accepts values must be boolean flags.",
                            )
                        )

        if "strict_unknown_attributes" in proposal_surface and not isinstance(
            proposal_surface.get("strict_unknown_attributes"),
            bool,
        ):
            issues.append(
                self._issue(
                    code="invalid_proposal_surface",
                    path="proposal_surface.strict_unknown_attributes",
                    message="proposal_surface.strict_unknown_attributes must be a boolean.",
                )
            )

        if "batch_mode" in proposal_surface and proposal_surface.get("batch_mode") not in {
            "atomic",
            "best_effort",
        }:
            issues.append(
                self._issue(
                    code="invalid_proposal_surface",
                    path="proposal_surface.batch_mode",
                    message="proposal_surface.batch_mode must be 'atomic' or 'best_effort'.",
                )
            )

    def _validate_attribute_definitions(
        self,
        raw_attributes: Any,
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> dict[str, dict[str, Any]]:
        attributes = self._require_mapping(raw_attributes, path, issues)
        if attributes is None:
            return {}

        attribute_definitions: dict[str, dict[str, Any]] = {}
        for attribute_name, raw_definition in attributes.items():
            attr_path = f"{path}.{attribute_name}"
            if not isinstance(attribute_name, str) or not attribute_name.strip():
                issues.append(
                    self._issue(
                        code="invalid_attribute_name",
                        path=path,
                        message="Attribute names must be non-empty strings.",
                    )
                )
                continue
            definition = self._require_mapping(raw_definition, attr_path, issues)
            if definition is None:
                continue

            self._check_unknown_keys(definition, _ATTRIBUTE_KEYS, attr_path, issues)
            self._check_required_keys(definition, ("type",), attr_path, issues)
            attr_type = definition.get("type")
            if attr_type not in _ATTRIBUTE_TYPES:
                issues.append(
                    self._issue(
                        code="invalid_attribute_type",
                        path=f"{attr_path}.type",
                        message=(
                            f"Attribute type must be one of {sorted(_ATTRIBUTE_TYPES)}, "
                            f"got {attr_type!r}."
                        ),
                    )
                )
            if "description" in definition and definition.get("description") is not None:
                self._require_non_empty_string(
                    definition.get("description"),
                    f"{attr_path}.description",
                    issues,
                )
            if "enum" in definition:
                enum_values = definition.get("enum")
                if not isinstance(enum_values, list) or not enum_values:
                    issues.append(
                        self._issue(
                            code="invalid_attribute_enum",
                            path=f"{attr_path}.enum",
                            message="Attribute enum must be a non-empty list.",
                        )
                    )
                else:
                    for index, enum_value in enumerate(enum_values):
                        if _is_blank(enum_value):
                            issues.append(
                                self._issue(
                                    code="invalid_attribute_enum",
                                    path=f"{attr_path}.enum[{index}]",
                                    message="Attribute enum values must be non-empty.",
                                )
                            )
            if "nullable" in definition and not isinstance(definition.get("nullable"), bool):
                issues.append(
                    self._issue(
                        code="invalid_nullable_flag",
                        path=f"{attr_path}.nullable",
                        message="Attribute nullable must be a boolean.",
                    )
                )

            attribute_definitions[attribute_name] = definition

        return attribute_definitions

    def _validate_required_attributes(
        self,
        raw_required_attributes: Any,
        *,
        available_attributes: set[str],
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        if not isinstance(raw_required_attributes, list):
            issues.append(
                self._issue(
                    code="invalid_required_attributes",
                    path=path,
                    message="required_attributes must be a list of non-empty strings.",
                )
            )
            return

        seen: set[str] = set()
        for index, attribute_name in enumerate(raw_required_attributes):
            item_path = f"{path}[{index}]"
            if not isinstance(attribute_name, str) or not attribute_name.strip():
                issues.append(
                    self._issue(
                        code="invalid_required_attributes",
                        path=item_path,
                        message="required_attributes entries must be non-empty strings.",
                    )
                )
                continue
            if attribute_name in seen:
                issues.append(
                    self._issue(
                        code="duplicate_required_attribute",
                        path=item_path,
                        message=f"required_attributes contains duplicate entry {attribute_name!r}.",
                    )
                )
                continue
            seen.add(attribute_name)
            if attribute_name not in available_attributes:
                issues.append(
                    self._issue(
                        code="unknown_required_attribute",
                        path=item_path,
                        message=(
                            f"required_attributes references unknown attribute {attribute_name!r}."
                        ),
                    )
                )

    def _validate_identity_rule(
        self,
        raw_identity_rule: Any,
        *,
        available_attributes: set[str],
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        identity_rule = self._require_mapping(raw_identity_rule, path, issues)
        if identity_rule is None:
            return

        mode = identity_rule.get("mode")
        if mode not in _IDENTITY_MODES:
            issues.append(
                self._issue(
                    code="invalid_identity_mode",
                    path=f"{path}.mode",
                    message=(
                        f"Identity mode must be one of {sorted(_IDENTITY_MODES)}, got {mode!r}."
                    ),
                )
            )
            return

        if mode == "external_id":
            self._check_unknown_keys(identity_rule, _EXTERNAL_IDENTITY_KEYS, path, issues)
            self._check_required_keys(identity_rule, ("mode", "field"), path, issues)
            field_name = self._require_non_empty_string(
                identity_rule.get("field"),
                f"{path}.field",
                issues,
            )
            if "prefix" in identity_rule:
                self._require_non_empty_string(
                    identity_rule.get("prefix"),
                    f"{path}.prefix",
                    issues,
                )
            if field_name is not None and not self._is_known_identity_field(
                field_name,
                available_attributes,
            ):
                issues.append(
                    self._issue(
                        code="unknown_identity_field",
                        path=f"{path}.field",
                        message=(
                            f"Identity field {field_name!r} is not declared as an attribute and is "
                            "not part of the reserved identity hint surface."
                        ),
                    )
                )
            return

        if mode == "hint_priority":
            self._check_unknown_keys(identity_rule, _HINT_PRIORITY_IDENTITY_KEYS, path, issues)
            self._check_required_keys(identity_rule, ("mode", "strategies", "fallback"), path, issues)
            fallback = identity_rule.get("fallback")
            if fallback not in _IDENTITY_FALLBACKS:
                issues.append(
                    self._issue(
                        code="invalid_identity_fallback",
                        path=f"{path}.fallback",
                        message=(
                            "Identity fallback must be one of "
                            f"{sorted(_IDENTITY_FALLBACKS)}, got {fallback!r}."
                        ),
                    )
                )

            strategies = identity_rule.get("strategies")
            if not isinstance(strategies, list) or not strategies:
                issues.append(
                    self._issue(
                        code="invalid_identity_strategies",
                        path=f"{path}.strategies",
                        message="hint_priority strategies must be a non-empty list.",
                    )
                )
                return

            seen_hints: set[str] = set()
            for index, raw_strategy in enumerate(strategies):
                strategy_path = f"{path}.strategies[{index}]"
                strategy = self._require_mapping(raw_strategy, strategy_path, issues)
                if strategy is None:
                    continue
                self._check_unknown_keys(
                    strategy,
                    _HINT_PRIORITY_STRATEGY_KEYS,
                    strategy_path,
                    issues,
                )
                hint = self._require_non_empty_string(
                    strategy.get("hint"),
                    f"{strategy_path}.hint",
                    issues,
                )
                if hint is not None:
                    if hint in seen_hints:
                        issues.append(
                            self._issue(
                                code="duplicate_identity_field",
                                path=f"{strategy_path}.hint",
                                message=f"Identity hint {hint!r} is duplicated.",
                            )
                        )
                    seen_hints.add(hint)
                    if not self._is_known_identity_field(hint, available_attributes):
                        issues.append(
                            self._issue(
                                code="unknown_identity_field",
                                path=f"{strategy_path}.hint",
                                message=(
                                    f"Identity hint {hint!r} is not declared as an attribute and "
                                    "is not part of the reserved identity hint surface."
                                ),
                            )
                        )
                if "prefix" in strategy:
                    self._require_non_empty_string(
                        strategy.get("prefix"),
                        f"{strategy_path}.prefix",
                        issues,
                    )
                if "description" in strategy and strategy.get("description") is not None:
                    self._require_non_empty_string(
                        strategy.get("description"),
                        f"{strategy_path}.description",
                        issues,
                    )
                if "normalization" in strategy:
                    self._validate_identity_normalization(
                        strategy.get("normalization"),
                        path=f"{strategy_path}.normalization",
                        issues=issues,
                    )
            return

        self._check_unknown_keys(identity_rule, _COMPOSITE_IDENTITY_KEYS, path, issues)
        self._check_required_keys(identity_rule, ("mode", "fields", "prefix"), path, issues)
        self._require_non_empty_string(
            identity_rule.get("prefix"),
            f"{path}.prefix",
            issues,
        )

        fields = identity_rule.get("fields")
        if not isinstance(fields, list) or not fields:
            issues.append(
                self._issue(
                    code="invalid_identity_fields",
                    path=f"{path}.fields",
                    message="Composite identity fields must be a non-empty list of strings.",
                )
            )
        else:
            seen_fields: set[str] = set()
            for index, field_name in enumerate(fields):
                field_path = f"{path}.fields[{index}]"
                if not isinstance(field_name, str) or not field_name.strip():
                    issues.append(
                        self._issue(
                            code="invalid_identity_fields",
                            path=field_path,
                            message="Composite identity fields must be non-empty strings.",
                        )
                    )
                    continue
                if field_name in seen_fields:
                    issues.append(
                        self._issue(
                            code="duplicate_identity_field",
                            path=field_path,
                            message=f"Composite identity field {field_name!r} is duplicated.",
                        )
                    )
                    continue
                seen_fields.add(field_name)
                if not self._is_known_identity_field(field_name, available_attributes):
                    issues.append(
                        self._issue(
                            code="unknown_identity_field",
                            path=field_path,
                            message=(
                                f"Identity field {field_name!r} is not declared as an attribute and "
                                "is not part of the reserved identity hint surface."
                            ),
                        )
                    )

        if "normalization" in identity_rule:
            self._validate_identity_normalization(
                identity_rule.get("normalization"),
                path=f"{path}.normalization",
                issues=issues,
            )

    def _validate_identity_normalization(
        self,
        normalization_rules: Any,
        *,
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        if not isinstance(normalization_rules, list):
            issues.append(
                self._issue(
                    code="invalid_identity_normalization",
                    path=path,
                    message="Identity normalization must be a list of supported rules.",
                )
            )
            return

        seen_rules: set[str] = set()
        for index, rule in enumerate(normalization_rules):
            rule_path = f"{path}[{index}]"
            if rule not in _IDENTITY_NORMALIZATION_RULES:
                issues.append(
                    self._issue(
                        code="invalid_identity_normalization",
                        path=rule_path,
                        message=(
                            "Identity normalization rules must be one of "
                            f"{sorted(_IDENTITY_NORMALIZATION_RULES)}, got {rule!r}."
                        ),
                    )
                )
                continue
            if rule in seen_rules:
                issues.append(
                    self._issue(
                        code="duplicate_identity_normalization",
                        path=rule_path,
                        message=f"Identity normalization rule {rule!r} is duplicated.",
                    )
                )
            seen_rules.add(rule)

    def _validate_merge_policy(
        self,
        raw_merge_policy: Any,
        *,
        attribute_definitions: dict[str, dict[str, Any]],
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        merge_policy = self._require_mapping(raw_merge_policy, path, issues)
        if merge_policy is None:
            return

        self._check_unknown_keys(merge_policy, _MERGE_POLICY_KEYS, path, issues)
        self._check_required_keys(
            merge_policy,
            ("mode", "conflict_strategy"),
            path,
            issues,
        )
        if merge_policy.get("mode") not in _MERGE_MODES:
            issues.append(
                self._issue(
                    code="invalid_merge_mode",
                    path=f"{path}.mode",
                    message=(
                        f"Merge mode must be one of {sorted(_MERGE_MODES)}, "
                        f"got {merge_policy.get('mode')!r}."
                    ),
                )
            )
        if merge_policy.get("conflict_strategy") not in _MERGE_CONFLICT_STRATEGIES:
            issues.append(
                self._issue(
                    code="invalid_conflict_strategy",
                    path=f"{path}.conflict_strategy",
                    message=(
                        "Merge conflict_strategy must be one of "
                        f"{sorted(_MERGE_CONFLICT_STRATEGIES)}, got "
                        f"{merge_policy.get('conflict_strategy')!r}."
                    ),
                )
            )
        if "source_timestamp_attribute" in merge_policy:
            field_name = self._require_non_empty_string(
                merge_policy.get("source_timestamp_attribute"),
                f"{path}.source_timestamp_attribute",
                issues,
            )
            if field_name is not None:
                attribute_definition = attribute_definitions.get(field_name)
                if attribute_definition is None:
                    issues.append(
                        self._issue(
                            code="unknown_merge_timestamp_attribute",
                            path=f"{path}.source_timestamp_attribute",
                            message=(
                                f"source_timestamp_attribute {field_name!r} is not declared in attributes."
                            ),
                        )
                    )
                elif attribute_definition.get("type") != "datetime":
                    issues.append(
                        self._issue(
                            code="invalid_merge_timestamp_attribute",
                            path=f"{path}.source_timestamp_attribute",
                            message=(
                                f"source_timestamp_attribute {field_name!r} must reference a datetime "
                                "attribute."
                            ),
                        )
                    )

    def _validate_relation_endpoint_list(
        self,
        raw_endpoint_types: Any,
        *,
        known_entity_types: set[str],
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        if not isinstance(raw_endpoint_types, list) or not raw_endpoint_types:
            issues.append(
                self._issue(
                    code="invalid_relation_endpoint",
                    path=path,
                    message="Relation endpoints must be non-empty lists of known entity types.",
                )
            )
            return

        seen_entity_types: set[str] = set()
        for index, entity_type in enumerate(raw_endpoint_types):
            item_path = f"{path}[{index}]"
            if not isinstance(entity_type, str) or not entity_type.strip():
                issues.append(
                    self._issue(
                        code="invalid_relation_endpoint",
                        path=item_path,
                        message="Relation endpoint entries must be non-empty strings.",
                    )
                )
                continue
            if entity_type in seen_entity_types:
                issues.append(
                    self._issue(
                        code="duplicate_relation_endpoint",
                        path=item_path,
                        message=f"Relation endpoint {entity_type!r} is duplicated.",
                    )
                )
                continue
            seen_entity_types.add(entity_type)
            if entity_type not in known_entity_types:
                issues.append(
                    self._issue(
                        code="unknown_relation_endpoint",
                        path=item_path,
                        message=(
                            f"Relation endpoint {entity_type!r} is not declared in entity_types."
                        ),
                    )
                )

    def _validate_projection_attribute_ref(
        self,
        *,
        entity_name: Any,
        attribute_name: Any,
        entity_attribute_index: dict[str, set[str]],
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        if not isinstance(entity_name, str) or entity_name not in entity_attribute_index:
            issues.append(
                self._issue(
                    code="invalid_projection_hint",
                    path=path,
                    message=f"Projection hint references unknown entity_type {entity_name!r}.",
                )
            )
            return
        if not isinstance(attribute_name, str) or attribute_name not in entity_attribute_index[entity_name]:
            issues.append(
                self._issue(
                    code="invalid_projection_hint",
                    path=path,
                    message=(
                        f"Projection hint references unknown attribute {attribute_name!r} "
                        f"for entity_type {entity_name!r}."
                    ),
                )
            )

    def _is_known_identity_field(
        self,
        field_name: str,
        available_attributes: set[str],
    ) -> bool:
        return field_name in available_attributes or field_name in _RESERVED_IDENTITY_FIELDS

    def _check_unknown_keys(
        self,
        data: dict[str, Any],
        allowed_keys: set[str],
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        for key in sorted(data):
            if key not in allowed_keys:
                issues.append(
                    self._issue(
                        code="unknown_field",
                        path=f"{path}.{key}" if path != "$" else key,
                        message=f"Unknown field {key!r} is not allowed at {path}.",
                    )
                )

    def _check_required_keys(
        self,
        data: dict[str, Any],
        required_keys: tuple[str, ...],
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        for key in required_keys:
            if key not in data:
                issues.append(
                    self._issue(
                        code="missing_required_field",
                        path=f"{path}.{key}" if path != "$" else key,
                        message=f"Missing required field {key!r} at {path}.",
                    )
                )

    def _require_mapping(
        self,
        value: Any,
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> dict[str, Any] | None:
        if not isinstance(value, Mapping):
            issues.append(
                self._issue(
                    code="invalid_shape",
                    path=path,
                    message=f"{path} must be a mapping.",
                )
            )
            return None
        return dict(value)

    def _require_non_empty_string(
        self,
        value: Any,
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> str | None:
        if not isinstance(value, str) or not value.strip():
            issues.append(
                self._issue(
                    code="invalid_string",
                    path=path,
                    message=f"{path} must be a non-empty string.",
                )
            )
            return None
        return value.strip()

    def _require_name_matches_key(
        self,
        value: Any,
        expected_name: str,
        path: str,
        issues: list[DomainPackValidationIssue],
    ) -> None:
        actual_name = self._require_non_empty_string(value, path, issues)
        if actual_name is not None and actual_name != expected_name:
            issues.append(
                self._issue(
                    code="name_key_mismatch",
                    path=path,
                    message=(
                        f"Definition name {actual_name!r} must match its mapping key "
                        f"{expected_name!r}."
                    ),
                )
            )

    def _issue(
        self,
        *,
        code: str,
        path: str,
        message: str,
        severity: str = "error",
        details: dict[str, Any] | None = None,
    ) -> DomainPackValidationIssue:
        issue: DomainPackValidationIssue = {
            "code": code,
            "path": path,
            "message": message,
            "severity": severity,
        }
        if details is not None:
            issue["details"] = details
        return issue

    def _report(
        self,
        issues: list[DomainPackValidationIssue],
    ) -> DomainPackValidationReport:
        errors = [issue for issue in issues if issue["severity"] == "error"]
        warnings = [issue for issue in issues if issue["severity"] == "warning"]
        return {
            "ok": len(errors) == 0,
            "issues": issues,
            "errors": errors,
            "warnings": warnings,
        }


class DefaultDomainPackCompatibilityChecker(DomainPackCompatibilityChecker):
    """Detect breaking or migration-relevant changes between two pack versions."""

    def compare(
        self,
        *,
        active_pack: DomainPack,
        candidate_pack: DomainPack,
    ) -> DomainPackCompatibilityReport:
        active_pack = normalize_domain_pack(active_pack)
        candidate_pack = normalize_domain_pack(candidate_pack)
        issues: list[DomainPackCompatibilityIssue] = []

        active_domain = _manifest_value(active_pack, "domain")
        candidate_domain = _manifest_value(candidate_pack, "domain")
        active_pack_version = _manifest_value(active_pack, "pack_version") or ""
        candidate_pack_version = _manifest_value(candidate_pack, "pack_version") or ""

        if active_domain != candidate_domain:
            issues.append(
                self._issue(
                    code="domain_mismatch",
                    path="manifest.domain",
                    message=(
                        f"Active pack domain {active_domain!r} does not match candidate domain "
                        f"{candidate_domain!r}."
                    ),
                    breaking=True,
                    migration_required=False,
                    old_value=active_domain,
                    new_value=candidate_domain,
                )
            )

        active_entities = _mapping(active_pack.get("entity_types"))
        candidate_entities = _mapping(candidate_pack.get("entity_types"))
        active_relations = _mapping(active_pack.get("relation_types"))
        candidate_relations = _mapping(candidate_pack.get("relation_types"))

        for entity_name in sorted(set(active_entities) - set(candidate_entities)):
            issues.append(
                self._issue(
                    code="entity_type_removed",
                    path=f"entity_types.{entity_name}",
                    message=f"Entity type {entity_name!r} was removed.",
                    breaking=True,
                    migration_required=True,
                )
            )

        for relation_name in sorted(set(active_relations) - set(candidate_relations)):
            issues.append(
                self._issue(
                    code="relation_type_removed",
                    path=f"relation_types.{relation_name}",
                    message=f"Relation type {relation_name!r} was removed.",
                    breaking=True,
                    migration_required=True,
                )
            )

        for entity_name in sorted(set(active_entities) & set(candidate_entities)):
            active_definition = _mapping(active_entities.get(entity_name))
            candidate_definition = _mapping(candidate_entities.get(entity_name))
            if not active_definition or not candidate_definition:
                continue

            active_identity = _normalize_identity_rule(active_definition.get("identity"))
            candidate_identity = _normalize_identity_rule(candidate_definition.get("identity"))
            if active_identity != candidate_identity:
                issues.append(
                    self._issue(
                        code="canonical_key_rule_changed",
                        path=f"entity_types.{entity_name}.identity",
                        message=(
                            f"Entity type {entity_name!r} changed its identity rule, which can "
                            "change canonical keys."
                        ),
                        breaking=True,
                        migration_required=True,
                        old_value=active_definition.get("identity"),
                        new_value=candidate_definition.get("identity"),
                    )
                )

            active_required = _string_list(active_definition.get("required_attributes"))
            candidate_required = _string_list(candidate_definition.get("required_attributes"))
            strengthened = sorted(set(candidate_required) - set(active_required))
            if strengthened:
                issues.append(
                    self._issue(
                        code="required_attributes_strengthened",
                        path=f"entity_types.{entity_name}.required_attributes",
                        message=(
                            f"Entity type {entity_name!r} added new required attributes "
                            f"{strengthened!r}."
                        ),
                        breaking=True,
                        migration_required=True,
                        old_value=active_required,
                        new_value=candidate_required,
                        details={"added_required_attributes": strengthened},
                    )
                )

        for relation_name in sorted(set(active_relations) & set(candidate_relations)):
            active_definition = _mapping(active_relations.get(relation_name))
            candidate_definition = _mapping(candidate_relations.get(relation_name))
            if not active_definition or not candidate_definition:
                continue

            active_from = set(_string_list(active_definition.get("from_entity_types")))
            active_to = set(_string_list(active_definition.get("to_entity_types")))
            candidate_from = set(_string_list(candidate_definition.get("from_entity_types")))
            candidate_to = set(_string_list(candidate_definition.get("to_entity_types")))

            if active_from != candidate_from or active_to != candidate_to:
                expanded = active_from.issubset(candidate_from) and active_to.issubset(candidate_to)
                issues.append(
                    self._issue(
                        code="relation_endpoints_expanded" if expanded else "relation_endpoints_changed",
                        path=f"relation_types.{relation_name}",
                        message=(
                            f"Relation type {relation_name!r} changed its endpoint entity types."
                        ),
                        breaking=not expanded,
                        review_required=expanded,
                        migration_required=not expanded,
                        old_value={
                            "from_entity_types": sorted(active_from),
                            "to_entity_types": sorted(active_to),
                        },
                        new_value={
                            "from_entity_types": sorted(candidate_from),
                            "to_entity_types": sorted(candidate_to),
                        },
                    )
                )

            active_cardinality = _normalize_cardinality(active_definition.get("cardinality"))
            candidate_cardinality = _normalize_cardinality(candidate_definition.get("cardinality"))
            if active_cardinality != candidate_cardinality:
                tightening = _is_cardinality_tightening(
                    active_cardinality=active_cardinality,
                    candidate_cardinality=candidate_cardinality,
                )
                issues.append(
                    self._issue(
                        code="relation_cardinality_changed",
                        path=f"relation_types.{relation_name}.cardinality",
                        message=(
                            f"Relation type {relation_name!r} changed cardinality from "
                            f"{active_cardinality!r} to {candidate_cardinality!r}."
                        ),
                        breaking=tightening,
                        review_required=not tightening,
                        migration_required=tightening,
                        old_value=active_cardinality,
                        new_value=candidate_cardinality,
                    )
                )

        breaking_changes = [issue for issue in issues if issue["breaking"]]
        review_required_issues = [issue for issue in issues if issue["review_required"]]
        return {
            "compatible": len(breaking_changes) == 0,
            "review_required": len(review_required_issues) > 0,
            "migration_required": any(issue["migration_required"] for issue in issues),
            "recommended_action": self._recommended_action(
                breaking_changes=breaking_changes,
                review_required_issues=review_required_issues,
            ),
            "active_pack_version": active_pack_version,
            "candidate_pack_version": candidate_pack_version,
            "issues": issues,
            "breaking_changes": breaking_changes,
            "review_required_issues": review_required_issues,
        }

    def _issue(
        self,
        *,
        code: str,
        path: str,
        message: str,
        breaking: bool,
        review_required: bool = False,
        migration_required: bool,
        old_value: Any | None = None,
        new_value: Any | None = None,
        details: dict[str, Any] | None = None,
    ) -> DomainPackCompatibilityIssue:
        issue: DomainPackCompatibilityIssue = {
            "code": code,
            "path": path,
            "message": message,
            "decision": self._decision(breaking=breaking, review_required=review_required),
            "breaking": breaking,
            "review_required": review_required,
            "migration_required": migration_required,
        }
        if old_value is not None:
            issue["old_value"] = old_value
        if new_value is not None:
            issue["new_value"] = new_value
        if details is not None:
            issue["details"] = details
        return issue

    def _decision(
        self,
        *,
        breaking: bool,
        review_required: bool,
    ) -> DomainPackCompatibilityDecision:
        if breaking:
            return "auto_block"
        if review_required:
            return "manual_review"
        return "auto_pass"

    def _recommended_action(
        self,
        *,
        breaking_changes: list[DomainPackCompatibilityIssue],
        review_required_issues: list[DomainPackCompatibilityIssue],
    ) -> DomainPackCompatibilityDecision:
        if breaking_changes:
            return "auto_block"
        if review_required_issues:
            return "manual_review"
        return "auto_pass"


class DefaultDomainPackApprovalService(DomainPackApprovalService):
    """Review and register packs through validator and compatibility gates."""

    def __init__(
        self,
        *,
        domain_pack_registry: DomainPackRegistry,
        validator: DomainPackValidator | None = None,
        compatibility_checker: DomainPackCompatibilityChecker | None = None,
        review_audit_repository: DomainPackReviewAuditRepository | None = None,
    ) -> None:
        self.domain_pack_registry = domain_pack_registry
        self.validator = validator or DefaultDomainPackValidator()
        self.compatibility_checker = compatibility_checker or DefaultDomainPackCompatibilityChecker()
        self.review_audit_repository = review_audit_repository

    def review_registration(
        self,
        candidate_pack: DomainPack,
        review_audit: DomainPackReviewAudit | None = None,
    ) -> DomainPackApprovalReport:
        normalized_candidate_pack = normalize_domain_pack(candidate_pack)
        report = self._build_review_report(
            normalized_candidate_pack,
            review_audit=review_audit,
        )
        self._persist_audit_record(
            action="review_registration",
            candidate_pack=normalized_candidate_pack,
            requested_activation=False,
            report=report,
        )
        return report

    def register_pack(
        self,
        candidate_pack: DomainPack,
        *,
        activate: bool = False,
        review_audit: DomainPackReviewAudit | None = None,
    ) -> DomainPackApprovalReport:
        normalized_candidate_pack = normalize_domain_pack(candidate_pack)
        report = self._build_review_report(
            normalized_candidate_pack,
            review_audit=review_audit,
        )
        if not report["validation"]["ok"]:
            report["ok"] = False
            self._persist_audit_record(
                action="register_pack",
                candidate_pack=normalized_candidate_pack,
                requested_activation=activate,
                report=report,
            )
            return report

        compatibility = report.get("compatibility")
        if activate and compatibility is not None and (
            not compatibility["compatible"] or not report["activation_safe"]
        ):
            report["ok"] = False
            report["activated"] = False
            self._persist_audit_record(
                action="register_pack",
                candidate_pack=normalized_candidate_pack,
                requested_activation=activate,
                report=report,
            )
            return report

        try:
            self.domain_pack_registry.register_approved(normalized_candidate_pack, activate=activate)
        except DomainPackRegistryError as exc:
            report["ok"] = False
            report["registration_error"] = self._registration_error(exc)
            self._persist_audit_record(
                action="register_pack",
                candidate_pack=normalized_candidate_pack,
                requested_activation=activate,
                report=report,
            )
            return report

        report["ok"] = True
        report["registered"] = True
        report["activated"] = activate
        self._persist_audit_record(
            action="register_pack",
            candidate_pack=normalized_candidate_pack,
            requested_activation=activate,
            report=report,
        )
        return report

    def _build_review_report(
        self,
        candidate_pack: DomainPack,
        *,
        review_audit: DomainPackReviewAudit | None,
    ) -> DomainPackApprovalReport:
        validation = self.validator.validate(candidate_pack)
        domain = _manifest_value(candidate_pack, "domain") or ""
        candidate_pack_version = _manifest_value(candidate_pack, "pack_version") or ""
        active_pack_version = self.domain_pack_registry.get_active_version(domain) if domain else None

        report: DomainPackApprovalReport = {
            "ok": validation["ok"],
            "domain": domain,
            "candidate_pack_version": candidate_pack_version,
            "validation": validation,
            "registered": False,
            "activated": False,
            "activation_safe": validation["ok"],
            "review_required": False,
            "recommended_action": "auto_pass",
        }
        normalized_review_audit = self._normalize_review_audit(review_audit)
        if normalized_review_audit:
            report["review_audit"] = normalized_review_audit
        if active_pack_version is not None:
            report["active_pack_version"] = active_pack_version

        if not validation["ok"] or not domain or active_pack_version is None:
            return report

        try:
            active_pack = self.domain_pack_registry.get(domain, active_pack_version)
        except DomainPackRegistryError as exc:
            report["ok"] = False
            report["activation_safe"] = False
            report["registration_error"] = self._registration_error(exc)
            return report

        if _manifest_value(active_pack, "pack_version") == candidate_pack_version:
            return report

        compatibility = self.compatibility_checker.compare(
            active_pack=active_pack,
            candidate_pack=candidate_pack,
        )
        report["compatibility"] = compatibility
        report["review_required"] = compatibility["review_required"]
        report["recommended_action"] = compatibility["recommended_action"]
        report["activation_safe"] = compatibility["compatible"] and (
            not compatibility["review_required"]
            or self._review_allows_activation(normalized_review_audit)
        )
        return report

    def _normalize_review_audit(
        self,
        review_audit: DomainPackReviewAudit | None,
    ) -> DomainPackReviewAudit | None:
        if review_audit is None:
            return None
        normalized: DomainPackReviewAudit = {}
        for key in ("reviewed_by", "reviewed_at", "decision_reason", "migration_plan_ref"):
            value = review_audit.get(key)
            if isinstance(value, str) and value.strip():
                normalized[key] = value.strip()
        if isinstance(review_audit.get("approved_for_activation"), bool):
            normalized["approved_for_activation"] = bool(review_audit["approved_for_activation"])
        return normalized or None

    def _review_allows_activation(
        self,
        review_audit: DomainPackReviewAudit | None,
    ) -> bool:
        return bool(review_audit and review_audit.get("approved_for_activation") is True)

    def _registration_error(
        self,
        exc: DomainPackRegistryError,
    ) -> DomainPackRegistrationError:
        return {
            "code": exc.code,
            "message": str(exc),
            "details": {
                "domain": exc.domain,
                "pack_version": exc.pack_version,
                "available_versions": exc.available_versions,
            },
        }

    def _persist_audit_record(
        self,
        *,
        action: str,
        candidate_pack: DomainPack,
        requested_activation: bool,
        report: DomainPackApprovalReport,
    ) -> None:
        if self.review_audit_repository is None:
            return
        record: DomainPackApprovalAuditRecord = {
            "action": action,  # type: ignore[typeddict-item]
            "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "domain": _manifest_value(candidate_pack, "domain") or "",
            "candidate_pack_version": _manifest_value(candidate_pack, "pack_version") or "",
            "requested_activation": requested_activation,
            "report": report,
        }
        record_id = self.review_audit_repository.append_record(record)
        report["audit_record_id"] = record_id


def _manifest_value(pack: DomainPack, key: str) -> str | None:
    if not isinstance(pack, Mapping):
        return None
    manifest = pack.get("manifest")
    if not isinstance(manifest, Mapping):
        return None
    value = manifest.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            values.append(item.strip())
    return values


def _normalize_identity_rule(value: Any) -> tuple[Any, ...]:
    if not isinstance(value, Mapping):
        return ("invalid",)
    mode = value.get("mode")
    if mode == "external_id":
        return (
            "external_id",
            value.get("field"),
            value.get("prefix"),
        )
    if mode == "composite":
        return (
            "composite",
            tuple(_string_list(value.get("fields"))),
            value.get("prefix"),
            tuple(_string_list(value.get("normalization"))),
        )
    if mode == "hint_priority":
        strategies = []
        for item in value.get("strategies") or []:
            if not isinstance(item, Mapping):
                continue
            strategies.append(
                (
                    item.get("hint"),
                    item.get("prefix"),
                    tuple(_string_list(item.get("normalization"))),
                )
            )
        return (
            "hint_priority",
            tuple(strategies),
            value.get("fallback"),
        )
    return ("invalid",)


def _normalize_cardinality(value: Any) -> str:
    if value in _RELATION_CARDINALITIES:
        return str(value)
    return "many_to_many"


def _is_cardinality_tightening(
    *,
    active_cardinality: str,
    candidate_cardinality: str,
) -> bool:
    return _CARDINALITY_ORDER[candidate_cardinality] < _CARDINALITY_ORDER[active_cardinality]


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
