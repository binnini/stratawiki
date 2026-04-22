from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from wiki_mcp.schemas.metadata_validation import ensure_personal_anchors
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.services.personal_document_bodies import PersonalDocumentBodyStore


class RuntimeContractError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = dict(details or {})


class PersonalDocumentValidationError(RuntimeContractError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="validation_error",
            status_code=422,
            details=details,
        )


class PersonalDocumentConflictError(RuntimeContractError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="conflict",
            status_code=409,
            details=details,
        )


class PersonalDocumentNotFoundError(RuntimeContractError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="not_found",
            status_code=404,
            details=details,
        )

@dataclass(slots=True)
class PersonalDocumentService:
    personal_repository: Any
    profile_context_repository: Any
    snapshot_repository: Any
    rendering_repository: Any

    def list_documents(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        subspace: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, object]:
        scope_ref = self._scope_ref(tenant_id=tenant_id, user_id=user_id)
        statuses = [status] if status else ["active"]
        records = self.personal_repository.list_records(
            domain=domain,
            scope_ref=scope_ref,
            kind=kind,
            statuses=statuses,
            limit=limit,
        )
        items = [self._document_from_record(record, scope_ref=scope_ref) for record in records]
        if subspace is not None:
            normalized_subspace = self._normalize_subspace(subspace)
            items = [item for item in items if item["subspace"] == normalized_subspace]
        return {"status": "ok", "items": items}

    def get_document(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        document_id: str,
    ) -> dict[str, object]:
        scope_ref = self._scope_ref(tenant_id=tenant_id, user_id=user_id)
        record = self._require_record(
            domain=domain,
            scope_ref=scope_ref,
            document_id=document_id,
        )
        return {
            "status": "ok",
            "document": self._document_from_record(record, scope_ref=scope_ref),
        }

    def create_document(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        profile_version: str,
        subspace: str,
        kind: str,
        title: str,
        body_markdown: str | None,
        asset_refs: list[str] | None,
        anchors: list[dict[str, str]] | None,
    ) -> dict[str, object]:
        normalized_subspace = self._normalize_subspace(subspace)
        normalized_title = self._required_string(title, key="title")
        normalized_kind = self._required_string(kind, key="kind")
        normalized_body = self._normalize_optional_string(body_markdown, key="body_markdown")
        normalized_asset_refs = self._normalize_asset_refs(asset_refs)
        normalized_anchors = ensure_personal_anchors(anchors or [], label="create_personal_document.anchors")
        self._validate_create_payload(body_markdown=normalized_body, asset_refs=normalized_asset_refs)
        self._require_profile_context(
            domain=domain,
            tenant_id=tenant_id,
            user_id=user_id,
            profile_version=profile_version,
        )

        scope_ref = self._scope_ref(tenant_id=tenant_id, user_id=user_id)
        now = self._now_iso()
        document_id = f"pdoc_{uuid.uuid4().hex[:12]}"
        snapshot_ref = self._snapshot_ref(domain=domain, profile_version=profile_version)
        record = self._build_record(
            document_id=document_id,
            domain=domain,
            scope_ref=scope_ref,
            snapshot_ref=snapshot_ref,
            profile_version=profile_version,
            subspace=normalized_subspace,
            kind=normalized_kind,
            title=normalized_title,
            body_markdown=normalized_body,
            asset_refs=normalized_asset_refs,
            anchors=normalized_anchors,
            status="active",
            version=1,
            created_at=now,
            updated_at=now,
        )
        receipt = self._body_store().replace_body_atomically(
            domain=domain,
            record_id=document_id,
            path=str(record["path"]),
            title=normalized_title,
            body_markdown=normalized_body or "",
            scope_ref=scope_ref,
            snapshot_ref=snapshot_ref,
        )
        try:
            self.personal_repository.save_record(record)
            self._body_store().commit_body_write(receipt)
        except Exception:
            self._body_store().rollback_body_write(receipt)
            raise
        return self.get_document(
            domain=domain,
            tenant_id=tenant_id,
            user_id=user_id,
            document_id=document_id,
        )

    def update_document(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        document_id: str,
        profile_version: str,
        if_version: int,
        title: str | None = None,
        body_markdown: str | None = None,
        anchors: list[dict[str, str]] | None = None,
        asset_refs: list[str] | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        scope_ref = self._scope_ref(tenant_id=tenant_id, user_id=user_id)
        current = self._require_record(
            domain=domain,
            scope_ref=scope_ref,
            document_id=document_id,
        )
        if current.get("status") == "deleted":
            raise PersonalDocumentValidationError(
                "Deleted Personal documents cannot be updated.",
                details={"resource": "personal_document", "document_id": document_id},
            )
        self._require_profile_context(
            domain=domain,
            tenant_id=tenant_id,
            user_id=user_id,
            profile_version=profile_version,
        )
        current_document = self._document_from_record(current, scope_ref=scope_ref)
        self._require_matching_version(document=current_document, if_version=if_version)

        next_title = self._normalize_optional_non_empty_string(title, key="title") if title is not None else current_document["title"]
        next_body = (
            self._normalize_optional_string(body_markdown, key="body_markdown")
            if body_markdown is not None
            else current_document["body_markdown"]
        )
        next_asset_refs = (
            self._normalize_asset_refs(asset_refs)
            if asset_refs is not None
            else list(current_document["asset_refs"])
        )
        next_anchors = (
            ensure_personal_anchors(anchors, label="update_personal_document.anchors")
            if anchors is not None
            else list(current_document["anchors"])
        )
        next_status = self._normalize_optional_status(status) if status is not None else current_document["status"]
        if title is None and body_markdown is None and anchors is None and asset_refs is None and status is None:
            raise PersonalDocumentValidationError(
                "update_personal_document requires at least one mutable field.",
                details={"invalid_fields": ["title", "body_markdown", "anchors", "asset_refs", "status"]},
            )
        self._validate_body_or_assets(body_markdown=next_body, asset_refs=next_asset_refs)

        updated_at = self._now_iso()
        record = self._build_record(
            document_id=document_id,
            domain=domain,
            scope_ref=scope_ref,
            snapshot_ref=self._snapshot_ref(domain=domain, profile_version=profile_version),
            profile_version=profile_version,
            subspace=current_document["subspace"],
            kind=current_document["kind"],
            title=next_title or current_document["title"],
            body_markdown=next_body,
            asset_refs=next_asset_refs,
            anchors=next_anchors,
            status=next_status,
            version=int(current_document["version"]) + 1,
            created_at=str(current_document["created_at"]),
            updated_at=updated_at,
        )
        receipt = self._body_store().replace_body_atomically(
            domain=domain,
            record_id=document_id,
            path=str(record["path"]),
            title=str(record["title"]),
            body_markdown=next_body or "",
            scope_ref=scope_ref,
            snapshot_ref=record["snapshot_ref"],
        )
        try:
            self.personal_repository.save_record(record)
            self._body_store().commit_body_write(receipt)
        except Exception:
            self._body_store().rollback_body_write(receipt)
            raise
        return self.get_document(
            domain=domain,
            tenant_id=tenant_id,
            user_id=user_id,
            document_id=document_id,
        )

    def delete_document(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        document_id: str,
        if_version: int,
    ) -> dict[str, object]:
        scope_ref = self._scope_ref(tenant_id=tenant_id, user_id=user_id)
        current = self._require_record(
            domain=domain,
            scope_ref=scope_ref,
            document_id=document_id,
        )
        current_document = self._document_from_record(current, scope_ref=scope_ref)
        self._require_matching_version(document=current_document, if_version=if_version)

        record = self._build_record(
            document_id=document_id,
            domain=domain,
            scope_ref=scope_ref,
            snapshot_ref=current["snapshot_ref"],
            profile_version=current["profile_version"],
            subspace=current_document["subspace"],
            kind=current_document["kind"],
            title=current_document["title"],
            body_markdown=current_document["body_markdown"],
            asset_refs=list(current_document["asset_refs"]),
            anchors=list(current_document["anchors"]),
            status="deleted",
            version=int(current_document["version"]) + 1,
            created_at=str(current_document["created_at"]),
            updated_at=self._now_iso(),
        )
        self.personal_repository.save_record(record)
        return self.get_document(
            domain=domain,
            tenant_id=tenant_id,
            user_id=user_id,
            document_id=document_id,
        )

    def _build_record(
        self,
        *,
        document_id: str,
        domain: str,
        scope_ref: ScopeRef,
        snapshot_ref: dict[str, str],
        profile_version: str,
        subspace: str,
        kind: str,
        title: str,
        body_markdown: str | None,
        asset_refs: list[str],
        anchors: list[dict[str, str]],
        status: str,
        version: int,
        created_at: str,
        updated_at: str,
    ) -> dict[str, Any]:
        return {
            "id": document_id,
            "layer": "personal",
            "domain": domain,
            "kind": kind,
            "title": title,
            "summary": self._summary(title=title, body_markdown=body_markdown),
            "scope_ref": dict(scope_ref),
            "snapshot_ref": dict(snapshot_ref),
            "profile_version": profile_version,
            "path": self._document_path(scope_ref=scope_ref, document_id=document_id),
            "subspace": subspace,
            "asset_refs": list(asset_refs),
            "content_hash": self._body_store().content_hash(body_markdown or ""),
            "anchors": list(anchors),
            "status": status,
            "schema_version": "personal.document.v1",
            "version": version,
            "created_at": created_at,
            "updated_at": updated_at,
            "provenance": {
                "generated_by": {"kind": "user"},
                "generated_at": updated_at,
            },
        }

    def _document_from_record(
        self,
        record: dict[str, Any],
        *,
        scope_ref: ScopeRef,
    ) -> dict[str, object]:
        body_result = self._body_store().read_body(
            path=self._record_path(record),
            scope_ref=scope_ref,
        )
        subspace = str(record.get("subspace") or "raw")
        asset_refs = record.get("asset_refs")
        if not isinstance(asset_refs, list):
            asset_refs = []
        return {
            "document_id": record["id"],
            "domain": record["domain"],
            "tenant_id": scope_ref["tenant_id"],
            "user_id": scope_ref["user_id"],
            "subspace": subspace,
            "kind": record["kind"],
            "title": record["title"],
            "body_markdown": body_result.body_markdown,
            "asset_refs": [str(value) for value in asset_refs if isinstance(value, str) and value.strip()],
            "anchors": list(record.get("anchors", [])),
            "based_on": dict(record["snapshot_ref"]),
            "provenance": dict(record.get("provenance", {})),
            "status": record["status"],
            "version": int(record.get("version") or 1),
            "created_at": str(record.get("created_at") or record.get("updated_at") or self._now_iso()),
            "updated_at": str(record.get("updated_at") or record.get("created_at") or self._now_iso()),
        }

    def _require_record(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        document_id: str,
    ) -> dict[str, Any]:
        records = self.personal_repository.get_by_ids([document_id], scope_ref)
        for record in records:
            if record.get("domain") == domain:
                return record
        raise PersonalDocumentNotFoundError(
            f"Unknown Personal document: {document_id}",
            details={"resource": "personal_document", "document_id": document_id},
        )

    def _require_profile_context(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        profile_version: str,
    ) -> dict[str, Any]:
        try:
            profile_context = self.profile_context_repository.get_profile_context(domain, tenant_id, user_id)
        except KeyError as exc:
            raise PersonalDocumentValidationError(
                "Personal document writes require an existing stored profile context.",
                details={
                    "domain": domain,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                },
            ) from exc
        if profile_context["profile_version"] != profile_version:
            raise PersonalDocumentValidationError(
                "Requested profile_version does not match the current stored profile context.",
                details={
                    "domain": domain,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "profile_version": profile_version,
                    "current_profile_version": profile_context["profile_version"],
                },
            )
        return profile_context

    def _require_matching_version(
        self,
        *,
        document: dict[str, object],
        if_version: int,
    ) -> None:
        if not isinstance(if_version, int) or if_version <= 0:
            raise PersonalDocumentValidationError(
                "if_version must be a positive integer.",
                details={"resource": "personal_document", "document_id": document["document_id"]},
            )
        current_version = int(document["version"])
        if if_version != current_version:
            raise PersonalDocumentConflictError(
                "Personal document version mismatch.",
                details={
                    "resource": "personal_document",
                    "document_id": document["document_id"],
                    "expected_version": if_version,
                    "current_version": current_version,
                },
            )

    def _snapshot_ref(self, *, domain: str, profile_version: str) -> dict[str, str]:
        status = self.snapshot_repository.get_snapshot_status(domain=domain, layer=None)
        layers = status.get("layers") if isinstance(status, dict) else {}
        fact_status = layers.get("fact") if isinstance(layers, dict) else None
        interpretation_status = layers.get("interpretation") if isinstance(layers, dict) else None
        fact_snapshot_id = (
            fact_status.get("fact_snapshot_id")
            if isinstance(fact_status, dict)
            else None
        )
        if not isinstance(fact_snapshot_id, str) or not fact_snapshot_id:
            raise PersonalDocumentValidationError(
                "Personal document writes require an active fact snapshot.",
                details={"domain": domain},
            )
        snapshot_ref: dict[str, str] = {
            "fact_snapshot_id": fact_snapshot_id,
            "profile_version": profile_version,
        }
        interpretation_snapshot_id = (
            interpretation_status.get("interpretation_snapshot_id")
            if isinstance(interpretation_status, dict)
            else None
        )
        if isinstance(interpretation_snapshot_id, str) and interpretation_snapshot_id:
            snapshot_ref["interpretation_snapshot_id"] = interpretation_snapshot_id
        return snapshot_ref

    def _scope_ref(self, *, tenant_id: str, user_id: str) -> ScopeRef:
        return {"scope": "user", "tenant_id": tenant_id, "user_id": user_id}

    def _document_path(self, *, scope_ref: ScopeRef, document_id: str) -> str:
        return f"wiki/users/{scope_ref['user_id']}/personal-documents/{document_id}.md"

    def _record_path(self, record: dict[str, Any]) -> str:
        path = record.get("path")
        if not isinstance(path, str) or not path:
            return self._document_path(
                scope_ref=record["scope_ref"],
                document_id=str(record["id"]),
            )
        return path

    def _body_store(self) -> PersonalDocumentBodyStore:
        return PersonalDocumentBodyStore(self.rendering_repository)

    def _summary(self, *, title: str, body_markdown: str | None) -> str:
        body = (body_markdown or "").strip()
        if not body:
            return title[:160]
        for line in body.splitlines():
            normalized = line.strip().lstrip("#").strip()
            if normalized:
                return normalized[:160]
        return title[:160]

    def _normalize_subspace(self, subspace: str) -> str:
        normalized = self._required_string(subspace, key="subspace").lower()
        if normalized not in {"raw", "wiki"}:
            raise PersonalDocumentValidationError(
                "subspace must be one of ['raw', 'wiki'].",
                details={"invalid_fields": ["subspace"]},
            )
        return normalized

    def _normalize_asset_refs(self, asset_refs: list[str] | None) -> list[str]:
        if asset_refs is None:
            return []
        if not isinstance(asset_refs, list):
            raise PersonalDocumentValidationError(
                "asset_refs must be a list of strings.",
                details={"invalid_fields": ["asset_refs"]},
            )
        normalized: list[str] = []
        for value in asset_refs:
            if not isinstance(value, str) or not value.strip():
                raise PersonalDocumentValidationError(
                    "asset_refs must contain only non-empty strings.",
                    details={"invalid_fields": ["asset_refs"]},
                )
            normalized.append(value.strip())
        return normalized

    def _normalize_optional_status(self, status: str) -> str:
        normalized = self._required_string(status, key="status").lower()
        if normalized not in {"active", "stale", "deleted"}:
            raise PersonalDocumentValidationError(
                "status must be one of ['active', 'stale', 'deleted'].",
                details={"invalid_fields": ["status"]},
            )
        return normalized

    def _validate_create_payload(
        self,
        *,
        body_markdown: str | None,
        asset_refs: list[str],
    ) -> None:
        self._validate_body_or_assets(body_markdown=body_markdown, asset_refs=asset_refs)

    def _validate_body_or_assets(
        self,
        *,
        body_markdown: str | None,
        asset_refs: list[str],
    ) -> None:
        if not body_markdown and not asset_refs:
            raise PersonalDocumentValidationError(
                "Personal documents require body_markdown or non-empty asset_refs.",
                details={"invalid_fields": ["body_markdown", "asset_refs"]},
            )

    def _required_string(self, value: str, *, key: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise PersonalDocumentValidationError(
                f"{key} must be a non-empty string.",
                details={"invalid_fields": [key]},
            )
        return value.strip()

    def _normalize_optional_non_empty_string(self, value: str | None, *, key: str) -> str | None:
        normalized = self._normalize_optional_string(value, key=key)
        if normalized is None:
            return None
        if not normalized:
            raise PersonalDocumentValidationError(
                f"{key} must be a non-empty string when provided.",
                details={"invalid_fields": [key]},
            )
        return normalized

    def _normalize_optional_string(self, value: str | None, *, key: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise PersonalDocumentValidationError(
                f"{key} must be a string when provided.",
                details={"invalid_fields": [key]},
            )
        return value.strip()

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
