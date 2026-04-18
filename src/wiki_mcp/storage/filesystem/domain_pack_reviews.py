from __future__ import annotations

import json
from hashlib import sha1
from pathlib import Path

from wiki_mcp.schemas.domain_pack_review import DomainPackApprovalAuditRecord


class FileSystemDomainPackReviewAuditRepository:
    """Append-only JSONL audit store for Domain Pack review and activation decisions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_record(self, record: DomainPackApprovalAuditRecord) -> str:
        stored = dict(record)
        record_id = str(
            stored.get("record_id")
            or self._build_record_id(
                action=str(stored.get("action") or ""),
                domain=str(stored.get("domain") or ""),
                candidate_pack_version=str(stored.get("candidate_pack_version") or ""),
                recorded_at=str(stored.get("recorded_at") or ""),
            )
        )
        stored["record_id"] = record_id
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(stored, sort_keys=True) + "\n")
        return record_id

    def _build_record_id(
        self,
        *,
        action: str,
        domain: str,
        candidate_pack_version: str,
        recorded_at: str,
    ) -> str:
        digest = sha1(
            f"{action}:{domain}:{candidate_pack_version}:{recorded_at}".encode("utf-8")
        ).hexdigest()[:12]
        return f"pack_audit:{digest}"
