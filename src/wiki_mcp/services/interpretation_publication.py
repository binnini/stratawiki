from __future__ import annotations

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

    def _new_interpretation_snapshot_id(self, record: InterpretationRecord) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        family = str(record.get("family") or "family")
        subject_id = str(record.get("subject_id") or "subject")
        return (
            f"interp_snap:{record['domain']}:{family}:{subject_id}:{timestamp}:{uuid4().hex[:8]}"
        )
