from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from wiki_mcp.cli import run_cli


def test_demo_cli_lists_tools_without_postgres(tmp_path: Path) -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        [
            "--demo",
            "--seed-path",
            "examples/demo/mvp-seed.json",
            "--render-root",
            str(tmp_path),
            "list-tools",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert [tool["name"] for tool in payload] == [
        "ingest_fact_batch",
        "get_fact_record",
        "build_interpretation_snapshot",
        "get_interpretation_record",
        "query_personal_knowledge",
        "get_snapshot_status",
    ]
    assert stderr.getvalue() == ""


def test_demo_mvp_runs_end_to_end_and_writes_personal_output(tmp_path: Path) -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        [
            "--demo",
            "--seed-path",
            "examples/demo/mvp-seed.json",
            "--render-root",
            str(tmp_path),
            "demo-mvp",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["status"] == "ok"
    steps = payload["steps"]
    assert steps["ingest_fact_batch"]["status"] == "ok"
    assert steps["build_interpretation_snapshot"]["status"] == "ok"
    assert steps["query_personal_knowledge"]["status"] == "ok"
    assert steps["get_snapshot_status"]["status"] == "ok"

    answer_markdown = steps["query_personal_knowledge"]["answer_markdown"]
    assert "## Strategy" in answer_markdown
    answers_dir = tmp_path / "wiki" / "users" / "user-1" / "answers"
    assert answers_dir.exists()
    persisted_files = list(answers_dir.glob("*.md"))
    assert persisted_files, "expected demo flow to persist a personal answer markdown file"
    persisted_body = persisted_files[0].read_text(encoding="utf-8")
    assert "stratawiki:personal_query_answer" in persisted_body
    assert stderr.getvalue() == ""
