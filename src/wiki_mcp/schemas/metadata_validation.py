from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wiki_mcp.schemas.interpretation_lifecycle import INTERPRETATION_LIFECYCLE_STATUSES


def ensure_non_empty_string(value: Any, *, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string.")


def ensure_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping.")
    return dict(value)


def ensure_scope_shape(
    *,
    scope: Any,
    tenant_id: Any = None,
    user_id: Any = None,
    label: str,
) -> None:
    if scope not in {"shared", "tenant", "user"}:
        raise ValueError(f"{label} has unsupported scope {scope!r}.")

    if scope == "shared":
        if tenant_id is not None or user_id is not None:
            raise ValueError(
                f"{label} uses shared scope but still carries tenant/user identifiers."
            )
        return

    if scope == "tenant":
        if not isinstance(tenant_id, str) or not tenant_id.strip() or user_id is not None:
            raise ValueError(
                f"{label} uses tenant scope but must include tenant_id and omit user_id."
            )
        return

    if (
        not isinstance(tenant_id, str)
        or not tenant_id.strip()
        or not isinstance(user_id, str)
        or not user_id.strip()
    ):
        raise ValueError(
            f"{label} uses user scope but must include both tenant_id and user_id."
        )


def ensure_scope_ref(scope_ref: Any, *, label: str) -> dict[str, Any]:
    scope_data = ensure_mapping(scope_ref, label=label)
    ensure_scope_shape(
        scope=scope_data.get("scope"),
        tenant_id=scope_data.get("tenant_id"),
        user_id=scope_data.get("user_id"),
        label=label,
    )
    return scope_data


def ensure_provenance(provenance: Any, *, label: str) -> dict[str, Any]:
    data = ensure_mapping(provenance, label=label)
    if not data:
        raise ValueError(f"{label} must not be empty.")

    if "generated_by" in data and data["generated_by"] is not None:
        generated_by = ensure_mapping(data["generated_by"], label=f"{label}.generated_by")
        ensure_non_empty_string(generated_by.get("kind"), label=f"{label}.generated_by.kind")

    if "generated_at" in data and data["generated_at"] is not None:
        ensure_non_empty_string(data["generated_at"], label=f"{label}.generated_at")

    return data


def ensure_snapshot_ref(snapshot_ref: Any, *, label: str) -> dict[str, Any]:
    data = ensure_mapping(snapshot_ref, label=label)
    ensure_non_empty_string(data.get("fact_snapshot_id"), label=f"{label}.fact_snapshot_id")

    for optional_key in (
        "interpretation_snapshot_id",
        "profile_version",
        "personal_snapshot_id",
    ):
        if optional_key in data and data[optional_key] is not None:
            ensure_non_empty_string(data[optional_key], label=f"{label}.{optional_key}")

    return data


def ensure_personal_anchors(value: Any, *, label: str) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list.")

    anchors: list[dict[str, str]] = []
    for index, item in enumerate(value):
        anchor = ensure_mapping(item, label=f"{label}[{index}]")
        ensure_non_empty_string(anchor.get("layer"), label=f"{label}[{index}].layer")
        if anchor["layer"] not in {"interpretation", "fact"}:
            raise ValueError(
                f"{label}[{index}].layer must be 'interpretation' or 'fact', got {anchor['layer']!r}."
            )
        ensure_non_empty_string(anchor.get("id"), label=f"{label}[{index}].id")
        anchors.append(
            {
                "layer": anchor["layer"].strip(),
                "id": anchor["id"].strip(),
            }
        )
    return anchors


def ensure_interpretation_status(status: Any, *, label: str) -> None:
    ensure_non_empty_string(status, label=label)
    if status not in INTERPRETATION_LIFECYCLE_STATUSES:
        raise ValueError(
            f"{label} must be one of {INTERPRETATION_LIFECYCLE_STATUSES}, got {status!r}."
        )
