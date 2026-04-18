from __future__ import annotations

from pathlib import Path

from wiki_mcp.storage.filesystem import FileSystemRenderingRepository


def test_read_body_returns_saved_markdown_when_scope_matches(tmp_path: Path) -> None:
    repository = FileSystemRenderingRepository(tmp_path)
    repository.write_artifact(
        {
            "domain": "recruiting",
            "layer": "personal",
            "record_id": "personal:1",
            "path": "wiki/users/user-1/answers/saved.md",
            "title": "Saved answer",
            "body_markdown": "## Answer\n\nSaved markdown body.",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
            "snapshot_ref": {"fact_snapshot_id": "fact_snap:1"},
        }
    )

    body = repository.read_body(
        path="wiki/users/user-1/answers/saved.md",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert body == "## Answer\n\nSaved markdown body."


def test_read_body_rejects_out_of_scope_user_path(tmp_path: Path) -> None:
    repository = FileSystemRenderingRepository(tmp_path)
    body = repository.read_body(
        path="wiki/users/user-2/answers/saved.md",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert body is None
