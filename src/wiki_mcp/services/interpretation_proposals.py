from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wiki_mcp.schemas import (
    INTERPRETATION_STATUS_PROPOSED,
    INTERPRETATION_STATUS_REJECTED,
    INTERPRETATION_STATUS_VALIDATED,
    FactRecord,
    InterpretationRecord,
    InterpretationValidationError,
    InterpretationValidationResult,
    ScopeRef,
    interpretation_support_links,
    materialize_interpretation_record,
)
from wiki_mcp.services.interpretation_families import (
    InterpretationFamilyRegistry,
    InterpretationProposalContext,
)
from wiki_mcp.services.interfaces.repositories import (
    FactRepository,
    InterpretationRepository,
)


class InterpretationProposalService:
    """Persist and validate proposal-shaped interpretation records."""

    def __init__(
        self,
        *,
        family_registry: InterpretationFamilyRegistry,
        interpretation_repository: InterpretationRepository,
        fact_repository: FactRepository,
    ) -> None:
        self.family_registry = family_registry
        self.interpretation_repository = interpretation_repository
        self.fact_repository = fact_repository

    def create_proposals(
        self,
        context: InterpretationProposalContext,
    ) -> list[InterpretationRecord]:
        proposals = [
            self._normalize_proposal(proposal, context)
            for proposal in self.family_registry.build_proposals(context)
        ]
        if proposals:
            self.interpretation_repository.save_records(
                proposals,
                {"fact_snapshot_id": context.fact_snapshot_id},
            )
        return proposals

    def validate_proposal(
        self,
        *,
        proposal_id: str,
        scope_ref: ScopeRef,
    ) -> InterpretationValidationResult:
        records = self.interpretation_repository.get_by_ids([proposal_id], scope_ref)
        if not records:
            return self._result(
                ok=False,
                record_id=proposal_id,
                status=INTERPRETATION_STATUS_REJECTED,
                errors=[
                    self._error(
                        code="proposal_not_found",
                        message=f"Interpretation proposal {proposal_id!r} was not found.",
                    )
                ],
            )

        record = dict(records[0])
        transition_errors = self._validate_transition(record)
        content_errors = self._validate_content(record, scope_ref=scope_ref)
        errors = [*transition_errors, *content_errors]
        if errors:
            next_status = (
                INTERPRETATION_STATUS_REJECTED
                if record["status"] in {INTERPRETATION_STATUS_PROPOSED, INTERPRETATION_STATUS_VALIDATED}
                else record["status"]
            )
            if next_status != record["status"]:
                record["status"] = next_status
                self.interpretation_repository.save_records(
                    [record],
                    {"fact_snapshot_id": record["fact_snapshot_id"]},
                )
            return self._result(
                ok=False,
                record_id=proposal_id,
                status=next_status,
                errors=errors,
            )

        record["status"] = INTERPRETATION_STATUS_VALIDATED
        self.interpretation_repository.save_records(
            [record],
            {"fact_snapshot_id": record["fact_snapshot_id"]},
        )
        return self._result(
            ok=True,
            record_id=proposal_id,
            status=INTERPRETATION_STATUS_VALIDATED,
            errors=[],
        )

    def _normalize_proposal(
        self,
        proposal: InterpretationRecord,
        context: InterpretationProposalContext,
    ) -> InterpretationRecord:
        normalized = dict(proposal)
        normalized["layer"] = "interpretation"
        normalized["domain"] = context.domain
        normalized["family"] = str(normalized.get("family") or context.family or "")
        normalized["subject_type"] = str(normalized.get("subject_type") or context.subject_type)
        normalized["subject_id"] = str(normalized.get("subject_id") or context.subject_id)
        if "subject" not in normalized and isinstance(context.subject, Mapping):
            normalized["subject"] = dict(context.subject)
        normalized["scope_ref"] = dict(context.scope_ref)
        normalized["schema_version"] = str(
            normalized.get("schema_version") or context.schema_version
        )
        normalized["fact_snapshot_id"] = str(
            normalized.get("fact_snapshot_id") or context.fact_snapshot_id
        )
        normalized["status"] = INTERPRETATION_STATUS_PROPOSED
        normalized["body"] = (
            dict(normalized["body"])
            if isinstance(normalized.get("body"), Mapping)
            else {}
        )
        normalized["render_hints"] = (
            dict(normalized["render_hints"])
            if isinstance(normalized.get("render_hints"), Mapping)
            else {}
        )
        if "provenance" not in normalized:
            normalized["provenance"] = dict(context.provenance)
        if "computed_at" not in normalized:
            generated_at = context.provenance.get("generated_at")
            if isinstance(generated_at, str) and generated_at.strip():
                normalized["computed_at"] = generated_at
        return materialize_interpretation_record(normalized)

    def _validate_transition(
        self,
        record: InterpretationRecord,
    ) -> list[InterpretationValidationError]:
        if record["status"] in {
            INTERPRETATION_STATUS_PROPOSED,
            INTERPRETATION_STATUS_VALIDATED,
        }:
            return []
        return [
            self._error(
                code="invalid_transition",
                field="status",
                message=(
                    "Only proposed or already validated interpretation records can be "
                    "validated."
                ),
                details={"current_status": record["status"]},
            )
        ]

    def _validate_content(
        self,
        record: InterpretationRecord,
        *,
        scope_ref: ScopeRef,
    ) -> list[InterpretationValidationError]:
        materialized = materialize_interpretation_record(record)
        errors: list[InterpretationValidationError] = []
        required_string_fields = (
            "id",
            "domain",
            "family",
            "kind",
            "subject_type",
            "subject_id",
            "schema_version",
            "fact_snapshot_id",
            "computed_at",
            "claim",
            "summary",
        )
        for field in required_string_fields:
            value = materialized.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    self._error(
                        code="missing_field",
                        field=field,
                        message=f"{field} must be a non-empty string before validation.",
                    )
                )

        if not isinstance(materialized.get("payload"), Mapping):
            errors.append(
                self._error(
                    code="invalid_payload",
                    field="payload",
                    message="payload must be a mapping before validation.",
                )
            )
        if not isinstance(materialized.get("body"), Mapping):
            errors.append(
                self._error(
                    code="invalid_body",
                    field="body",
                    message="body must be a mapping before validation.",
                )
            )
        if not isinstance(materialized.get("render_hints"), Mapping):
            errors.append(
                self._error(
                    code="invalid_render_hints",
                    field="render_hints",
                    message="render_hints must be a mapping before validation.",
                )
            )
        if not isinstance(materialized.get("scope_ref"), Mapping):
            errors.append(
                self._error(
                    code="invalid_scope_ref",
                    field="scope_ref",
                    message="scope_ref must be present before validation.",
                )
            )
        if not isinstance(materialized.get("provenance"), Mapping) or not materialized["provenance"]:
            errors.append(
                self._error(
                    code="missing_provenance",
                    field="provenance",
                    message="provenance must be attached before validation.",
                )
            )

        confidence = materialized.get("confidence")
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            errors.append(
                self._error(
                    code="invalid_confidence",
                    field="confidence",
                    message="confidence must be a number between 0 and 1.",
                )
            )

        support_links = interpretation_support_links(materialized)
        if not support_links:
            errors.append(
                self._error(
                    code="support_links_required",
                    field="support_links",
                    message="At least one support link is required before validation.",
                )
            )
            return errors

        fact_ids: list[str] = []
        for index, item in enumerate(support_links):
            if not isinstance(item, Mapping):
                errors.append(
                    self._error(
                        code="invalid_support_link",
                        field=f"support_links[{index}]",
                        message="Each support link must be a mapping.",
                    )
                )
                continue
            if item.get("target_layer") == "relation":
                support_ref = item.get("support_ref")
                if not isinstance(support_ref, Mapping) or not support_ref:
                    errors.append(
                        self._error(
                            code="invalid_relation_support_ref",
                            field=f"support_links[{index}].support_ref",
                            message="Relation support links must include support_ref metadata.",
                        )
                    )
                continue
            fact_id = item.get("target_id")
            if not isinstance(fact_id, str) or not fact_id.strip():
                support_ref = item.get("support_ref")
                if isinstance(support_ref, Mapping):
                    raw_fact_id = support_ref.get("fact_id")
                    if isinstance(raw_fact_id, str) and raw_fact_id.strip():
                        fact_id = raw_fact_id.strip()
            if not isinstance(fact_id, str) or not fact_id.strip():
                errors.append(
                    self._error(
                        code="missing_fact_id",
                        field=f"support_links[{index}].target_id",
                        message="Fact support links must include a non-empty target_id.",
                    )
                )
                continue
            fact_ids.append(fact_id)

        if not fact_ids:
            return errors

        facts = self.fact_repository.get_by_ids(fact_ids, scope_ref)
        found_ids = {fact["id"] for fact in facts}
        missing_ids = [fact_id for fact_id in fact_ids if fact_id not in found_ids]
        for fact_id in missing_ids:
            errors.append(
                self._error(
                    code="evidence_fact_not_found",
                    field="evidence",
                    message=f"Evidence fact {fact_id!r} does not exist in scope.",
                    details={"fact_id": fact_id},
                )
            )
        return errors

    def _error(
        self,
        *,
        code: str,
        message: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> InterpretationValidationError:
        error: InterpretationValidationError = {
            "code": code,
            "message": message,
        }
        if field is not None:
            error["field"] = field
        if details:
            error["details"] = details
        return error

    def _result(
        self,
        *,
        ok: bool,
        record_id: str,
        status: str,
        errors: list[InterpretationValidationError],
    ) -> InterpretationValidationResult:
        return {
            "ok": ok,
            "record_id": record_id,
            "status": status,  # type: ignore[typeddict-item]
            "errors": errors,
            "warnings": [],
        }
