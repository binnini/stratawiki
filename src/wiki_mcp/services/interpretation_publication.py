from __future__ import annotations

from difflib import SequenceMatcher
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from wiki_mcp.schemas import (
    INTERPRETATION_STATUS_PUBLISHED,
    INTERPRETATION_STATUS_STALE,
    INTERPRETATION_STATUS_SUPERSEDED,
    INTERPRETATION_STATUS_VALIDATED,
    InterpretationRecord,
    ScopeRef,
)
from wiki_mcp.services.interfaces.repositories import (
    InterpretationRepository,
    SnapshotRepository,
)
from wiki_mcp.services.interpretation_proposals import InterpretationProposalService


class InterpretationPublicationService:
    """Promote validated proposals into published shared interpretation state."""

    def __init__(
        self,
        *,
        proposal_service: InterpretationProposalService,
        interpretation_repository: InterpretationRepository,
        snapshot_repository: SnapshotRepository,
    ) -> None:
        self.proposal_service = proposal_service
        self.interpretation_repository = interpretation_repository
        self.snapshot_repository = snapshot_repository

    def publish_proposal(
        self,
        *,
        proposal_id: str,
        scope_ref: ScopeRef,
    ) -> dict[str, Any]:
        validation = self.proposal_service.validate_proposal(
            proposal_id=proposal_id,
            scope_ref=scope_ref,
        )
        if not validation["ok"]:
            return {
                "ok": False,
                "record_id": proposal_id,
                "status": validation["status"],
                "errors": validation["errors"],
            }

        current = self.interpretation_repository.get_by_ids([proposal_id], scope_ref)
        if not current:
            return {
                "ok": False,
                "record_id": proposal_id,
                "status": validation["status"],
                "errors": [
                    {
                        "code": "proposal_not_found_after_validation",
                        "message": f"Interpretation proposal {proposal_id!r} disappeared before publish.",
                    }
                ],
            }

        record = dict(current[0])
        if record["status"] != INTERPRETATION_STATUS_VALIDATED:
            return {
                "ok": False,
                "record_id": proposal_id,
                "status": record["status"],
                "errors": [
                    {
                        "code": "proposal_not_validated",
                        "field": "status",
                        "message": "Only validated interpretation proposals can be published.",
                    }
                ],
            }

        prior_records = self.interpretation_repository.list_records(
            domain=record["domain"],
            scope_ref=scope_ref,
            family=record.get("family"),
            kind=record.get("kind"),
            subject_type=record.get("subject_type"),
            subject_id=record.get("subject_id"),
            statuses=[
                INTERPRETATION_STATUS_PUBLISHED,
                INTERPRETATION_STATUS_STALE,
            ],
            limit=20,
        )
        duplicate_result = self._handle_partition_duplicates(
            record=record,  # type: ignore[arg-type]
            prior_records=prior_records,
        )
        if duplicate_result is not None:
            return duplicate_result

        superseded_ids: list[str] = []
        records_to_save: list[InterpretationRecord] = []
        for prior in prior_records:
            if prior["id"] == record["id"]:
                continue
            next_prior = dict(prior)
            next_prior["status"] = INTERPRETATION_STATUS_SUPERSEDED
            records_to_save.append(next_prior)  # type: ignore[arg-type]
            superseded_ids.append(prior["id"])

        interpretation_snapshot_id = self._new_interpretation_snapshot_id(record)
        record["status"] = INTERPRETATION_STATUS_PUBLISHED
        record["interpretation_snapshot_id"] = interpretation_snapshot_id
        records_to_save.append(record)  # type: ignore[arg-type]

        snapshot_ref = {
            "fact_snapshot_id": record["fact_snapshot_id"],
            "interpretation_snapshot_id": interpretation_snapshot_id,
        }
        self.interpretation_repository.save_records(records_to_save, snapshot_ref)
        self.snapshot_repository.publish_snapshot(
            "interpretation",
            record["domain"],
            snapshot_ref,
        )

        return {
            "ok": True,
            "record_id": record["id"],
            "status": INTERPRETATION_STATUS_PUBLISHED,
            "interpretation_snapshot_id": interpretation_snapshot_id,
            "superseded_ids": superseded_ids,
            "record": record,
        }

    def _handle_partition_duplicates(
        self,
        *,
        record: InterpretationRecord,
        prior_records: list[InterpretationRecord],
    ) -> dict[str, Any] | None:
        published_records = [
            prior
            for prior in prior_records
            if prior["id"] != record["id"] and prior["status"] == INTERPRETATION_STATUS_PUBLISHED
        ]
        if not published_records:
            return None

        for prior in published_records:
            if self._duplicate_key(prior) and self._duplicate_key(prior) == self._duplicate_key(record):
                next_record = dict(record)
                next_record["status"] = INTERPRETATION_STATUS_SUPERSEDED
                self.interpretation_repository.save_records(
                    [next_record],  # type: ignore[arg-type]
                    {"fact_snapshot_id": record["fact_snapshot_id"]},
                )
                return {
                    "ok": False,
                    "record_id": record["id"],
                    "status": INTERPRETATION_STATUS_SUPERSEDED,
                    "errors": [
                        {
                            "code": "duplicate_published_interpretation",
                            "field": "claim",
                            "message": (
                                "A published interpretation with the same normalized claim already "
                                "exists in this family partition."
                            ),
                        }
                    ],
                    "duplicate_of": prior["id"],
                }

        for prior in published_records:
            if self._is_near_duplicate(record, prior):
                return {
                    "ok": False,
                    "record_id": record["id"],
                    "status": record["status"],
                    "errors": [
                        {
                            "code": "near_duplicate_published_interpretation",
                            "field": "claim",
                            "message": (
                                "A near-duplicate published interpretation already exists in this "
                                "family partition. Leave the alternative validated until it is "
                                "explicitly reviewed."
                            ),
                        }
                    ],
                    "duplicate_of": prior["id"],
                }
        return None

    def _is_near_duplicate(
        self,
        current: InterpretationRecord,
        prior: InterpretationRecord,
    ) -> bool:
        current_text = self._comparison_text(current)
        prior_text = self._comparison_text(prior)
        if not current_text or not prior_text or current_text == prior_text:
            return False
        return SequenceMatcher(a=current_text, b=prior_text).ratio() >= 0.82

    def _comparison_text(self, record: InterpretationRecord) -> str:
        return self._normalize_text(
            " ".join(
                str(record.get(key) or "")
                for key in ("title", "claim", "summary")
            )
        )

    def _duplicate_key(self, record: InterpretationRecord) -> str:
        for key in ("claim", "summary", "title"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return self._normalize_text(value)
        return ""

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.lower().split())

    def _new_interpretation_snapshot_id(self, record: InterpretationRecord) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        family = str(record.get("family") or "family")
        subject_id = str(record.get("subject_id") or "subject")
        return (
            f"interp_snap:{record['domain']}:{family}:{subject_id}:{timestamp}:{uuid4().hex[:8]}"
        )
