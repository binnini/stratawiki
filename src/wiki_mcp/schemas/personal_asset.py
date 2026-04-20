from __future__ import annotations

from typing import NotRequired, TypedDict


class PersonalAssetRecord(TypedDict):
    """User-scoped Personal asset registration metadata."""

    asset_id: str
    domain: str
    tenant_id: str
    user_id: str
    asset_kind: str
    media_type: str
    filename: str
    storage_ref: str
    blob_sha256: NotRequired[str]
    size_bytes: NotRequired[int]
    identity_key: str
    status: str
    extraction_status: str
    schema_version: str
    created_at: NotRequired[str]
    updated_at: NotRequired[str]
