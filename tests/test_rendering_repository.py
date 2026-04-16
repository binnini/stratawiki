from __future__ import annotations

from pathlib import Path

from wiki_mcp.storage.filesystem.rendering import (
    FilesystemAndPostgresRenderingRepository,
)


class FakeCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.rowcount = 0

    def execute(self, query: str, params: object = None) -> None:
        normalized = " ".join(query.split())
        self.calls.append((normalized, params))
        if normalized.startswith("UPDATE graph.rendered_page"):
            self.rowcount = 0
        else:
            self.rowcount = 1

    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[object]:
        return []


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1



def test_rendering_repository_writes_file_and_upserts_rendered_page(tmp_path: Path) -> None:
    connection = FakeConnection()
    repository = FilesystemAndPostgresRenderingRepository(tmp_path, connection)

    stored_path = repository.write_artifact(
        {
            "domain": "recruiting",
            "layer": "personal",
            "record_id": "personal:plan-1",
            "path": "wiki/personal/tenant-1/user-1/plan-1.md",
            "title": "Backend transition plan",
            "body_markdown": "# Backend transition plan\n",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:new",
                "interpretation_snapshot_id": "interp_snap:new",
                "profile_version": "profile-v2",
            },
        }
    )

    assert Path(stored_path).read_text(encoding="utf-8") == "# Backend transition plan\n"
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert len(connection.cursor_instance.calls) == 2
    update_query, update_params = connection.cursor_instance.calls[0]
    insert_query, insert_params = connection.cursor_instance.calls[1]
    assert update_query.startswith("UPDATE graph.rendered_page")
    assert insert_query.startswith("INSERT INTO graph.rendered_page")
    assert update_params[5:8] == ("recruiting", "personal", "personal:plan-1")
    assert insert_params[0:4] == (
        "recruiting",
        "personal",
        "personal:plan-1",
        "wiki/personal/tenant-1/user-1/plan-1.md",
    )
