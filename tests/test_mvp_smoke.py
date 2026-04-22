from __future__ import annotations

from pathlib import Path

from wiki_mcp.demo import load_demo_seed
from wiki_mcp.server import build_server


def test_demo_server_smoke_covers_fact_interpretation_personal_and_snapshot(
    tmp_path: Path,
) -> None:
    seed = load_demo_seed("examples/demo/mvp-seed.json")
    server = build_server(
        demo_mode=True,
        render_root=str(tmp_path),
        seed_path="examples/demo/mvp-seed.json",
    )

    try:
        ingest = server.call_tool(
            "ingest_fact_batch",
            {
                "domain": seed.demo_query["domain"],
                "source_records": seed.source_records,
            },
        )
        assert ingest["status"] == "ok"
        assert "fact:job_posting:EMP-DEMO-1" in ingest["affected_fact_ids"]

        build = server.call_tool(
            "build_interpretation_snapshot",
            {
                "domain": seed.demo_query["domain"],
                "partition": seed.demo_partition,
                "fact_ids": ingest["affected_fact_ids"],
                "fact_snapshot": ingest["fact_snapshot"],
                "model_profile": seed.demo_query["model_profile"],
                "publish": True,
            },
        )
        assert build["status"] == "ok"

        answer = server.call_tool(
            "query_personal_knowledge",
            dict(seed.demo_query),
        )
        assert answer["status"] == "ok"
        assert answer["provenance"]["fact_snapshot"] == ingest["fact_snapshot"]
        assert answer["provenance"]["interpretation_snapshot"]
        assert "## Strategy" in answer["answer_markdown"]

        snapshot = server.call_tool(
            "get_snapshot_status",
            {
                "domain": seed.demo_query["domain"],
                "partition": {"family": seed.demo_partition["family"]},
            },
        )
        assert snapshot["status"] == "ok"
        assert snapshot["fact_snapshot"] == ingest["fact_snapshot"]
        assert snapshot["interpretation_snapshot"] == answer["provenance"]["interpretation_snapshot"]

        shared_page = (
            tmp_path
            / "wiki"
            / "shared"
            / "interpretations"
            / "market_trend"
            / "backend-japan-midlevel.md"
        )
        assert shared_page.exists()
        assert "Production AI delivery demand is rising" in shared_page.read_text(
            encoding="utf-8"
        )

        personal_pages = list((tmp_path / "wiki" / "users" / "user-1" / "answers").glob("*.md"))
        assert personal_pages
        assert personal_pages[0].read_text(encoding="utf-8").startswith("##")
    finally:
        server.close()
