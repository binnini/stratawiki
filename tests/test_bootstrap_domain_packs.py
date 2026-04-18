from __future__ import annotations

import json
from pathlib import Path

from wiki_mcp.bootstrap import bootstrap_application


def _external_pack() -> dict[str, object]:
    return {
        "manifest": {
            "domain": "recruiting",
            "packVersion": "2026-04-18",
            "status": "active",
            "compatibility": {"minStrataWikiVersion": "0.2.0"},
            "owner": {"system": "jobs-wiki"},
        },
        "entityTypes": {
            "job_posting": {
                "name": "job_posting",
                "attributes": {
                    "title": {"type": "string"},
                },
                "requiredAttributes": ["title"],
                "identity": {
                    "mode": "hint_priority",
                    "strategies": [{"hint": "source_id", "prefix": "job_posting"}],
                    "fallback": "reject",
                },
                "mergePolicy": {
                    "mode": "upsert",
                    "conflictStrategy": "prefer_newer_source",
                },
            }
        },
        "relationTypes": {},
    }


def test_bootstrap_loads_and_activates_domain_pack_artifact_in_demo_mode(tmp_path: Path) -> None:
    pack_path = tmp_path / "recruiting-v1.json"
    pack_path.write_text(json.dumps(_external_pack()), encoding="utf-8")

    context = bootstrap_application(
        demo_mode=True,
        render_root=tmp_path,
        seed_path="examples/demo/mvp-seed.json",
        domain_pack_paths=[pack_path],
    )
    try:
        assert context.domain_pack_registry.get_active_version("recruiting") == "2026-04-18"
        assert context.domain_proposal_ingestion_service is not None
        assert context.domain_pack_load_reports is not None
        assert context.domain_pack_load_reports[0]["report"]["ok"] is True
        review_log = tmp_path / "domain-pack-reviews.jsonl"
        assert review_log.exists()
    finally:
        context.close()
