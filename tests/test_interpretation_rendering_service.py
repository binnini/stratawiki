from __future__ import annotations

from pathlib import Path
from typing import Any

from wiki_mcp.services.interpretation_rendering import InterpretationRenderingService
from wiki_mcp.storage.filesystem import FileSystemRenderingRepository


class StubInterpretationRepository:
    def __init__(self, records: dict[str, dict[str, Any]]) -> None:
        self.records = dict(records)

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(self.records[record_id]) for record_id in ids if record_id in self.records]


def _published_market_trend(record_id: str, *, status: str = "published") -> dict[str, Any]:
    return {
        "id": record_id,
        "layer": "interpretation",
        "domain": "recruiting",
        "family": "market_trend",
        "kind": "market_trend",
        "subject_type": "market_segment",
        "subject_id": "backend-japan-midlevel",
        "scope_ref": {"scope": "shared"},
        "schema_version": "interpretation.v2",
        "status": status,
        "confidence": 0.82,
        "fact_snapshot_id": "fact_snap:seed",
        "interpretation_snapshot_id": "interp_snap:seed",
        "computed_at": "2026-04-18T00:00:00Z",
        "expires_at": "2026-04-19T00:00:00Z",
        "title": "Demand is rising",
        "claim": "Production AI demand is rising.",
        "summary": "Demand is rising for backend roles with production AI exposure.",
        "body": {"signals": ["llm"], "observations": [], "counterpoints": []},
        "evidence": [{"fact_id": "fact:job:1", "weight": 1.0, "role": "primary"}],
        "provenance": {"generated_by": {"kind": "llm"}},
        "render_hints": {"page_family": "market_trend", "page_key": "backend-japan-midlevel"},
    }


def test_render_shared_market_trend_page_writes_readable_published_artifact(
    tmp_path: Path,
) -> None:
    repository = StubInterpretationRepository(
        {"interp:published:1": _published_market_trend("interp:published:1")}
    )
    rendering_repository = FileSystemRenderingRepository(tmp_path)
    service = InterpretationRenderingService(
        interpretation_repository=repository,
        rendering_repository=rendering_repository,
    )

    page = service.render_shared_page(
        record_id="interp:published:1",
        scope_ref={"scope": "shared"},
    )

    assert page is not None
    assert page["path"] == "wiki/shared/interpretations/market_trend/backend-japan-midlevel.md"
    assert page["metadata"] == {
        "page_family": "market_trend",
        "page_key": "backend-japan-midlevel",
        "interpretation_ids": ["interp:published:1"],
        "render_template_version": "market_trend.shared.v1",
    }
    assert "Interpretation Snapshot: `interp_snap:seed`" in page["body_markdown"]
    assert "Interpretation IDs: `interp:published:1`" in page["body_markdown"]

    stored_page = rendering_repository.get_page(
        domain="recruiting",
        layer="interpretation",
        record_id="interp:published:1",
        scope_ref={"scope": "shared"},
    )

    assert stored_page is not None
    assert stored_page["snapshot_ref"]["interpretation_snapshot_id"] == "interp_snap:seed"
    assert stored_page["metadata"]["interpretation_ids"] == ["interp:published:1"]
    assert stored_page["body_markdown"].startswith("# Demand is rising")

    summaries = rendering_repository.list_pages(
        domain="recruiting",
        scope_ref={"scope": "shared"},
        layer="interpretation",
    )
    assert summaries == [
        {
            "domain": "recruiting",
            "layer": "interpretation",
            "record_id": "interp:published:1",
            "path": "wiki/shared/interpretations/market_trend/backend-japan-midlevel.md",
            "title": "Demand is rising",
            "scope_ref": {"scope": "shared"},
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:seed",
                "interpretation_snapshot_id": "interp_snap:seed",
            },
            "metadata": {
                "page_family": "market_trend",
                "page_key": "backend-japan-midlevel",
                "interpretation_ids": ["interp:published:1"],
                "render_template_version": "market_trend.shared.v1",
            },
        }
    ]


def test_render_shared_page_skips_non_published_records(tmp_path: Path) -> None:
    repository = StubInterpretationRepository(
        {"interp:validated:1": _published_market_trend("interp:validated:1", status="validated")}
    )
    rendering_repository = FileSystemRenderingRepository(tmp_path)
    service = InterpretationRenderingService(
        interpretation_repository=repository,
        rendering_repository=rendering_repository,
    )

    page = service.render_shared_page(
        record_id="interp:validated:1",
        scope_ref={"scope": "shared"},
    )

    assert page is None
    assert rendering_repository.list_pages(
        domain="recruiting",
        scope_ref={"scope": "shared"},
        layer="interpretation",
    ) == []
