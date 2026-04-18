from __future__ import annotations

import json
import os
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wiki_mcp.schemas.domain_pack_review import DomainPackApprovalReport
from wiki_mcp.services.domain_contract_normalization import normalize_domain_pack
from wiki_mcp.services.interfaces.domain_pack_governance import DomainPackApprovalService

DEFAULT_DOMAIN_PACK_PATHS_ENV = "STRATAWIKI_DOMAIN_PACK_PATHS"
DEFAULT_ACTIVE_DOMAIN_PACKS_ENV = "STRATAWIKI_ACTIVE_DOMAIN_PACKS"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _manifest_value(pack: Mapping[str, Any], key: str) -> str | None:
    manifest = pack.get("manifest")
    if not isinstance(manifest, Mapping):
        return None
    value = manifest.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def resolve_domain_pack_paths(
    domain_pack_paths: Iterable[str | Path] | None = None,
) -> list[Path]:
    if domain_pack_paths is not None:
        return [Path(path).expanduser().resolve() for path in domain_pack_paths]

    raw = os.environ.get(DEFAULT_DOMAIN_PACK_PATHS_ENV, "")
    if not raw.strip():
        return []
    return [Path(part).expanduser().resolve() for part in raw.split(os.pathsep) if part.strip()]


def resolve_active_domain_pack_versions(
    active_domain_pack_versions: Mapping[str, str] | None = None,
) -> dict[str, str]:
    if active_domain_pack_versions is not None:
        return {
            str(domain).strip(): str(pack_version).strip()
            for domain, pack_version in active_domain_pack_versions.items()
            if str(domain).strip() and str(pack_version).strip()
        }

    raw = os.environ.get(DEFAULT_ACTIVE_DOMAIN_PACKS_ENV, "")
    if not raw.strip():
        return {}

    resolved: dict[str, str] = {}
    for item in raw.split(","):
        if "=" not in item:
            continue
        domain, pack_version = item.split("=", 1)
        if domain.strip() and pack_version.strip():
            resolved[domain.strip()] = pack_version.strip()
    return resolved


def load_and_register_domain_packs(
    *,
    approval_service: DomainPackApprovalService,
    domain_pack_paths: Iterable[str | Path] | None = None,
    active_domain_pack_versions: Mapping[str, str] | None = None,
    review_log_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    paths = resolve_domain_pack_paths(domain_pack_paths)
    if not paths:
        return []

    artifacts: list[dict[str, Any]] = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError(f"Domain pack artifact at {path} must decode to an object.")
        normalized = normalize_domain_pack(raw)
        domain = _manifest_value(normalized, "domain") or ""
        pack_version = _manifest_value(normalized, "pack_version") or ""
        artifacts.append(
            {
                "path": str(path),
                "raw": dict(raw),
                "normalized": normalized,
                "domain": domain,
                "pack_version": pack_version,
                "status": _manifest_value(normalized, "status") or "",
            }
        )

    requested_active_versions = resolve_active_domain_pack_versions(active_domain_pack_versions)
    default_active_versions = _default_active_versions(artifacts)
    target_active_versions = {**default_active_versions, **requested_active_versions}

    reports: list[dict[str, Any]] = []
    review_log = Path(review_log_path).expanduser().resolve() if review_log_path else None
    if review_log is not None:
        review_log.parent.mkdir(parents=True, exist_ok=True)

    for artifact in artifacts:
        activate = target_active_versions.get(artifact["domain"]) == artifact["pack_version"]
        review_audit = {
            "reviewed_by": "bootstrap",
            "reviewed_at": _utc_now(),
            "decision_reason": f"Loaded domain pack artifact from {artifact['path']}.",
            **({"approved_for_activation": True} if activate else {}),
        }
        report = approval_service.register_pack(
            artifact["raw"],
            activate=activate,
            review_audit=review_audit,
        )
        if not report.get("ok", False):
            raise RuntimeError(
                "Failed to register domain pack artifact "
                f"{artifact['path']}: {json.dumps(report, sort_keys=True)}"
            )
        enriched_report = {
            "path": artifact["path"],
            "domain": artifact["domain"],
            "pack_version": artifact["pack_version"],
            "activated": activate,
            "report": report,
        }
        reports.append(enriched_report)
        if review_log is not None:
            with review_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(enriched_report, sort_keys=True) + "\n")
    return reports


def _default_active_versions(artifacts: list[dict[str, Any]]) -> dict[str, str]:
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for artifact in artifacts:
        domain = str(artifact.get("domain") or "").strip()
        if not domain:
            continue
        by_domain[domain].append(artifact)

    active_versions: dict[str, str] = {}
    for domain, domain_artifacts in by_domain.items():
        active_candidates = [
            artifact for artifact in domain_artifacts if artifact.get("status") == "active"
        ]
        if len(active_candidates) == 1:
            active_versions[domain] = str(active_candidates[0]["pack_version"])
            continue
        if len(domain_artifacts) == 1:
            active_versions[domain] = str(domain_artifacts[0]["pack_version"])
    return active_versions
