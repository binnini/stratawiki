from __future__ import annotations

import pytest

from wiki_mcp.services.personal_assets import (
    PersonalAssetConflictError,
    PersonalAssetNotFoundError,
    PersonalAssetRegistrationService,
    PersonalAssetValidationError,
)


class StubAssetRepository:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, object]] = {}
        self.identity_to_asset_id: dict[str, str] = {}

    def create_record(self, record: dict[str, object]) -> dict[str, object]:
        identity_key = str(record["identity_key"])
        existing_id = self.identity_to_asset_id.get(identity_key)
        if existing_id is not None:
            raise PersonalAssetConflictError(
                "Personal asset is already registered for this user scope.",
                details={"asset_id": existing_id},
            )
        self.identity_to_asset_id[identity_key] = str(record["asset_id"])
        stored = dict(record)
        self.records[str(record["asset_id"])] = stored
        return stored


class StubProfileContextRepository:
    def __init__(self, *, exists: bool = True) -> None:
        self.exists = exists

    def get_profile_context(self, domain: str, tenant_id: str, user_id: str) -> dict[str, object]:
        if not self.exists:
            raise KeyError("missing profile context")
        return {
            "domain": domain,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "profile_version": "profile:v1",
            "goals": [],
            "preferences": {},
            "attributes": {},
        }


def _payload() -> dict[str, object]:
    return {
        "domain": "recruiting",
        "tenant_id": "tenant-a",
        "user_id": "user-42",
        "asset_kind": "file",
        "media_type": "application/pdf",
        "filename": "resume.pdf",
        "blob_sha256": "sha256:abc123",
        "size_bytes": 248192,
        "storage_ref": "s3://bucket/resume.pdf",
    }


def test_register_personal_asset_issues_stable_asset_id() -> None:
    payload = _payload()
    first = PersonalAssetRegistrationService(
        asset_repository=StubAssetRepository(),
        profile_context_repository=StubProfileContextRepository(),
    )
    second = PersonalAssetRegistrationService(
        asset_repository=StubAssetRepository(),
        profile_context_repository=StubProfileContextRepository(),
    )

    first_result = first.register_personal_asset(payload)
    second_result = second.register_personal_asset(payload)

    assert first_result["asset_id"] == second_result["asset_id"]
    assert str(first_result["asset_id"]).startswith("passet_")
    assert first_result["asset"]["extraction_status"] == "not_requested"
    assert first_result["asset"]["status"] == "active"


def test_register_personal_asset_raises_conflict_with_existing_asset_id() -> None:
    service = PersonalAssetRegistrationService(
        asset_repository=StubAssetRepository(),
        profile_context_repository=StubProfileContextRepository(),
    )

    first = service.register_personal_asset(_payload())

    with pytest.raises(PersonalAssetConflictError) as exc_info:
        service.register_personal_asset(_payload())

    assert exc_info.value.code == "conflict"
    assert exc_info.value.details["asset_id"] == first["asset_id"]


def test_register_personal_asset_validates_scope_and_storage_ref() -> None:
    missing_scope_service = PersonalAssetRegistrationService(
        asset_repository=StubAssetRepository(),
        profile_context_repository=StubProfileContextRepository(exists=False),
    )
    with pytest.raises(PersonalAssetNotFoundError) as missing_scope:
        missing_scope_service.register_personal_asset(_payload())
    assert missing_scope.value.code == "not_found"

    invalid_storage_service = PersonalAssetRegistrationService(
        asset_repository=StubAssetRepository(),
        profile_context_repository=StubProfileContextRepository(),
    )
    invalid_payload = _payload()
    invalid_payload["storage_ref"] = "relative/path.pdf"
    with pytest.raises(PersonalAssetValidationError) as invalid_storage:
        invalid_storage_service.register_personal_asset(invalid_payload)
    assert invalid_storage.value.code == "validation_error"
