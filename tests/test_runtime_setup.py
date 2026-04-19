from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from wiki_mcp.cli import run_cli
from wiki_mcp.runtime_setup import apply_postgres_bootstrap, run_mvp_seed_flow


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object | None]] = []
        self.rowcount = 0

    def execute(self, query: str, params: object | None = None) -> None:
        self.executed.append((query, params))

    def fetchone(self) -> object | None:
        return None

    def fetchall(self) -> list[object]:
        return []


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakeProfileContextRepository:
    def __init__(self) -> None:
        self.saved_profiles: list[dict[str, Any]] = []

    def save_profile_context(self, profile: dict[str, Any]) -> None:
        self.saved_profiles.append(dict(profile))


class FakeServer:
    def __init__(self) -> None:
        self.bootstrap = SimpleNamespace(
            profile_context_repository=FakeProfileContextRepository()
        )
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.closed = False

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> dict[str, object]:
        self.calls.append((name, arguments))
        if name == "ingest_fact_batch":
            return {
                "status": "ok",
                "fact_snapshot": "fact_snap:recruiting:seed",
                "affected_fact_ids": ["fact:demo:1"],
            }
        if name == "build_interpretation_snapshot":
            return {
                "status": "ok",
                "interpretation_snapshot": "interp_snap:recruiting:seed",
            }
        if name == "query_personal_knowledge":
            return {
                "status": "ok",
                "answer_markdown": "## Strategy",
            }
        if name == "get_snapshot_status":
            return {
                "status": "ok",
                "fact_snapshot": "fact_snap:recruiting:seed",
                "interpretation_snapshot": "interp_snap:recruiting:seed",
            }
        raise AssertionError(f"Unexpected tool call: {name}")

    def close(self) -> None:
        self.closed = True


def test_apply_postgres_bootstrap_executes_sql_and_closes_connection(tmp_path: Path) -> None:
    sql_path = tmp_path / "bootstrap.sql"
    sql_path.write_text("CREATE SCHEMA IF NOT EXISTS test_schema;", encoding="utf-8")
    connection = FakeConnection()

    result = apply_postgres_bootstrap(
        database_url="postgresql://example/test",
        bootstrap_sql_path=sql_path,
        connect=lambda database_url: connection,
    )

    assert result == {"status": "ok", "bootstrap_sql_path": str(sql_path)}
    assert connection.cursor_instance.executed == [
        ("CREATE SCHEMA IF NOT EXISTS test_schema;", None)
    ]
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed is True


def test_run_mvp_seed_flow_persists_profiles_and_runs_tool_sequence() -> None:
    server = FakeServer()

    result = run_mvp_seed_flow(
        server,
        seed_path=Path("examples/demo/mvp-seed.json"),
    )

    profile_repository = server.bootstrap.profile_context_repository
    assert len(profile_repository.saved_profiles) == 1
    assert profile_repository.saved_profiles[0]["profile_version"] == "profile:v1"
    assert [name for name, _ in server.calls] == [
        "ingest_fact_batch",
        "build_interpretation_snapshot",
        "query_personal_knowledge",
        "get_snapshot_status",
    ]
    assert result["status"] == "ok"
    assert result["seeded_profiles"] == 1
    assert result["steps"]["query_personal_knowledge"]["status"] == "ok"


def test_init_db_cli_uses_database_bootstrapper_without_creating_server() -> None:
    stdout = StringIO()
    stderr = StringIO()
    captured: dict[str, object] = {}

    def fake_bootstrapper(*, database_url: str | None, bootstrap_sql_path: str | None) -> dict[str, object]:
        captured["database_url"] = database_url
        captured["bootstrap_sql_path"] = bootstrap_sql_path
        return {"status": "ok", "bootstrap_sql_path": str(bootstrap_sql_path)}

    exit_code = run_cli(
        [
            "--database-url",
            "postgresql://example/test",
            "init-db",
        ],
        server_factory=lambda **kwargs: (_ for _ in ()).throw(AssertionError("server should not be created")),
        database_bootstrapper=fake_bootstrapper,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert captured["database_url"] == "postgresql://example/test"
    assert str(captured["bootstrap_sql_path"]).endswith("config/postgres/bootstrap.sql")
    assert json.loads(stdout.getvalue())["status"] == "ok"
    assert stderr.getvalue() == ""


def test_seed_mvp_cli_uses_seed_runner_and_closes_server() -> None:
    stdout = StringIO()
    stderr = StringIO()
    fake_server = FakeServer()

    exit_code = run_cli(
        ["seed-mvp"],
        server_factory=lambda **kwargs: fake_server,
        mvp_seed_runner=lambda server, *, seed_path: {"status": "ok", "seed_path": str(seed_path)},
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {
        "seed_path": "examples/demo/mvp-seed.json",
        "status": "ok",
    }
    assert stderr.getvalue() == ""
    assert fake_server.closed is True


def test_seed_mvp_cli_rejects_demo_mode() -> None:
    stdout = StringIO()
    stderr = StringIO()

    with pytest.raises(SystemExit) as exc_info:
        run_cli(
            ["--demo", "seed-mvp"],
            stdout=stdout,
            stderr=stderr,
        )

    assert exc_info.value.code == 2
