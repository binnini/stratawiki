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
        "validate_domain_proposal_batch",
        "ingest_domain_proposal_batch",
        "get_fact_record",
        "build_interpretation_snapshot",
        "get_interpretation_record",
        "upsert_profile_context",
        "query_personal_knowledge",
        "get_snapshot_status",
    ]
    tool_by_name = {tool["name"]: tool for tool in payload}
    assert tool_by_name["ingest_fact_batch"]["contract_status"] == "legacy_transition"
    assert tool_by_name["ingest_fact_batch"]["recommended_for_external_clients"] is False
    assert tool_by_name["validate_domain_proposal_batch"]["contract_status"] == "preferred_external_write"
    assert tool_by_name["validate_domain_proposal_batch"]["recommended_for_external_clients"] is True
    assert tool_by_name["ingest_domain_proposal_batch"]["contract_status"] == "preferred_external_write"
    assert tool_by_name["ingest_domain_proposal_batch"]["recommended_for_external_clients"] is True
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


def test_demo_cli_validates_and_ingests_external_domain_proposal_example(tmp_path: Path) -> None:
    validation_stdout = StringIO()
    validation_stderr = StringIO()

    validation_exit_code = run_cli(
        [
            "--demo",
            "--render-root",
            str(tmp_path),
            "--domain-pack-path",
            "examples/domain-packs/recruiting.v2026-04-18.json",
            "call",
            "validate_domain_proposal_batch",
            "--args-file",
            "examples/integration/recruiting-domain-proposal-batch.json",
        ],
        stdout=validation_stdout,
        stderr=validation_stderr,
    )

    assert validation_exit_code == 0
    validation_payload = json.loads(validation_stdout.getvalue())
    assert validation_payload["ok"] is True
    assert validation_payload["committed"] is False
    assert validation_payload["audit"]["evaluated_pack_version"] == "2026-04-18"
    assert validation_stderr.getvalue() == ""

    ingest_stdout = StringIO()
    ingest_stderr = StringIO()
    ingest_exit_code = run_cli(
        [
            "--demo",
            "--render-root",
            str(tmp_path),
            "--domain-pack-path",
            "examples/domain-packs/recruiting.v2026-04-18.json",
            "call",
            "ingest_domain_proposal_batch",
            "--args-file",
            "examples/integration/recruiting-domain-proposal-batch.json",
        ],
        stdout=ingest_stdout,
        stderr=ingest_stderr,
    )

    assert ingest_exit_code == 0
    ingest_payload = json.loads(ingest_stdout.getvalue())
    assert ingest_payload["ok"] is True
    assert ingest_payload["committed"] is True
    assert "fact:job_posting:EMP-1" in ingest_payload["affected_fact_ids"]
    assert ingest_stderr.getvalue() == ""
