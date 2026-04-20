from __future__ import annotations

import hashlib
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from wiki_mcp.schemas.metadata_validation import ensure_non_empty_string
from wiki_mcp.schemas.personal_asset import PersonalAssetRecord


class PersonalAssetRegistrationError(Exception):
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
        self.details = details or {}


class PersonalAssetValidationError(PersonalAssetRegistrationError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="validation_error",
            status_code=int(HTTPStatus.UNPROCESSABLE_ENTITY),
            details=details,
        )


class PersonalAssetConflictError(PersonalAssetRegistrationError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="conflict",
            status_code=int(HTTPStatus.CONFLICT),
            details=details,
        )


class PersonalAssetNotFoundError(PersonalAssetRegistrationError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="not_found",
            status_code=int(HTTPStatus.NOT_FOUND),
            details=details,
        )


class PersonalAssetTemporarilyUnavailableError(PersonalAssetRegistrationError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="temporarily_unavailable",
            status_code=int(HTTPStatus.SERVICE_UNAVAILABLE),
            details=details,
        )


@dataclass(slots=True)
class PersonalAssetRegistrationService:
    asset_repository: Any
    profile_context_repository: Any

    def register_personal_asset(self, arguments: dict[str, object]) -> dict[str, object]:
        domain = self._required_string(arguments, "domain")
        tenant_id = self._required_string(arguments, "tenant_id")
        user_id = self._required_string(arguments, "user_id")
        asset_kind = self._required_string(arguments, "asset_kind")
        media_type = self._required_string(arguments, "media_type")
        filename = self._required_string(arguments, "filename")
        storage_ref = self._required_string(arguments, "storage_ref")
        blob_sha256 = self._optional_string(arguments, "blob_sha256")
        size_bytes = self._optional_size_bytes(arguments)

        if asset_kind != "file":
            raise PersonalAssetValidationError(
                "asset_kind must be 'file'.",
                details={"fields": [{"field": "asset_kind", "reason": "unsupported_value"}]},
            )
        if "/" not in media_type:
            raise PersonalAssetValidationError(
                "media_type must be a valid MIME type.",
                details={"fields": [{"field": "media_type", "reason": "invalid_media_type"}]},
            )
        if not self._is_valid_storage_ref(storage_ref):
            raise PersonalAssetValidationError(
                "storage_ref must be an absolute opaque locator.",
                details={"fields": [{"field": "storage_ref", "reason": "invalid_storage_ref"}]},
            )
        if blob_sha256 is not None and not blob_sha256.startswith("sha256:"):
            raise PersonalAssetValidationError(
                "blob_sha256 must use the 'sha256:' prefix.",
                details={"fields": [{"field": "blob_sha256", "reason": "invalid_sha256"}]},
            )

        self._require_owner_scope(domain=domain, tenant_id=tenant_id, user_id=user_id)
        identity_key = self._identity_key(
            domain=domain,
            tenant_id=tenant_id,
            user_id=user_id,
            blob_sha256=blob_sha256,
            storage_ref=storage_ref,
        )
        asset_id = self._stable_asset_id(identity_key)
        record: PersonalAssetRecord = {
            "asset_id": asset_id,
            "domain": domain,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "asset_kind": asset_kind,
            "media_type": media_type,
            "filename": filename,
            "storage_ref": storage_ref,
            "identity_key": identity_key,
            "status": "active",
            "extraction_status": "not_requested",
            "schema_version": "personal_asset.v1",
            **({"blob_sha256": blob_sha256} if blob_sha256 is not None else {}),
            **({"size_bytes": size_bytes} if size_bytes is not None else {}),
        }
        try:
            created = self.asset_repository.create_record(record)
        except PersonalAssetConflictError:
            raise
        except Exception as exc:
            raise PersonalAssetTemporarilyUnavailableError(
                "Personal asset registry is unavailable.",
                details={"retryable": True},
            ) from exc

        return {
            "status": "ok",
            "asset": created,
            "asset_id": created["asset_id"],
        }

    def _require_owner_scope(self, *, domain: str, tenant_id: str, user_id: str) -> None:
        try:
            self.profile_context_repository.get_profile_context(domain, tenant_id, user_id)
        except KeyError as exc:
            raise PersonalAssetNotFoundError(
                "Referenced user scope does not exist.",
                details={
                    "domain": domain,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                },
            ) from exc

    def _required_string(self, arguments: dict[str, object], field: str) -> str:
        value = arguments.get(field)
        try:
            ensure_non_empty_string(value, label=field)
        except ValueError as exc:
            raise PersonalAssetValidationError(
                str(exc),
                details={"fields": [{"field": field, "reason": "required"}]},
            ) from exc
        return str(value).strip()

    def _optional_string(self, arguments: dict[str, object], field: str) -> str | None:
        value = arguments.get(field)
        if value is None:
            return None
        try:
            ensure_non_empty_string(value, label=field)
        except ValueError as exc:
            raise PersonalAssetValidationError(
                str(exc),
                details={"fields": [{"field": field, "reason": "invalid"}]},
            ) from exc
        return str(value).strip()

    def _optional_size_bytes(self, arguments: dict[str, object]) -> int | None:
        value = arguments.get("size_bytes")
        if value is None:
            return None
        if not isinstance(value, int) or value < 0:
            raise PersonalAssetValidationError(
                "size_bytes must be a non-negative integer.",
                details={"fields": [{"field": "size_bytes", "reason": "invalid_size"}]},
            )
        return value

    def _identity_key(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        blob_sha256: str | None,
        storage_ref: str,
    ) -> str:
        identity_basis = blob_sha256 or storage_ref
        return f"{domain}:{tenant_id}:{user_id}:{identity_basis}"

    def _stable_asset_id(self, identity_key: str) -> str:
        digest = hashlib.sha256(identity_key.encode("utf-8")).hexdigest()[:24]
        return f"passet_{digest}"

    def _is_valid_storage_ref(self, storage_ref: str) -> bool:
        prefix, _, suffix = storage_ref.partition("://")
        return bool(prefix and suffix)
