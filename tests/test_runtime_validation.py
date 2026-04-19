from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from wiki_mcp.runtime_validation import (
    REQUIRED_BOOTSTRAP_RELATIONS,
    validate_runtime_prerequisites,
)


class FakeValidationCursor:
    def __init__(self, relations: set[str]) -> None:
        self.relations = relations
        self.last_relation: str | None = None
        self.rowcount = 0

    def execute(self, query: str, params: object | None = None) -> None:
        del query
        if not isinstance(params, tuple) or not params:
            self.last_relation = None
            return
        self.last_relation = str(params[0])

    def fetchone(self) -> dict[str, Any]:
        relation_name = (
            self.last_relation if self.last_relation in self.relations else None
        )
        return {"relation_name": relation_name}

    def fetchall(self) -> list[object]:
        return []


class FakeValidationConnection:
    def __init__(self, relations: set[str]) -> None:
        self.cursor_instance = FakeValidationCursor(relations)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> FakeValidationCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def test_validate_runtime_prerequisites_accepts_bootstrapped_runtime(tmp_path: Path) -> None:
    pack_path = tmp_path / "recruiting.json"
    pack_path.write_text('{"manifest":{"domain":"recruiting"}}', encoding="utf-8")
    render_root = tmp_path / "render"
    connection = FakeValidationConnection(set(REQUIRED_BOOTSTRAP_RELATIONS))

    result = validate_runtime_prerequisites(
        database_url="postgresql://example/test",
        render_root=render_root,
        domain_pack_paths=[pack_path],
        connect=lambda database_url: connection,
    )

    assert result["status"] == "ok"
    assert result["render_root"] == str(render_root.resolve())
    assert result["domain_pack_paths"] == [str(pack_path.resolve())]
    assert render_root.exists()
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed is True


def test_validate_runtime_prerequisites_rejects_missing_bootstrap_tables(
    tmp_path: Path,
) -> None:
    connection = FakeValidationConnection(
        {
            "fact.record_envelopes",
            "fact.relation_envelopes",
        }
    )

    with pytest.raises(ValueError) as exc_info:
        validate_runtime_prerequisites(
            database_url="postgresql://example/test",
            render_root=tmp_path / "render",
            connect=lambda database_url: connection,
        )

    message = str(exc_info.value)
    assert "Postgres runtime is missing bootstrap tables" in message
    assert "Run `stratawiki init-db`" in message
