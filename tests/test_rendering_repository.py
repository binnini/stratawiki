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


def test_atomic_artifact_replacement_can_commit_and_cleanup_backup(tmp_path: Path) -> None:
    repository = FileSystemRenderingRepository(tmp_path)
    repository.write_artifact(
        {
            "domain": "recruiting",
            "layer": "interpretation",
            "record_id": "interp:1",
            "path": "wiki/shared/interpretations/market_trend/backend.md",
            "title": "Old page",
            "body_markdown": "old body",
            "scope_ref": {"scope": "shared"},
            "snapshot_ref": {"fact_snapshot_id": "fact_snap:1"},
        }
    )

    receipt = repository.replace_artifact_atomically(
        {
            "domain": "recruiting",
            "layer": "interpretation",
            "record_id": "interp:2",
            "path": "wiki/shared/interpretations/market_trend/backend.md",
            "title": "New page",
            "body_markdown": "new body",
            "scope_ref": {"scope": "shared"},
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:2",
                "interpretation_snapshot_id": "interp_snap:2",
            },
        }
    )
    repository.commit_artifact_replacement(receipt)

    stored = (tmp_path / "wiki" / "shared" / "interpretations" / "market_trend" / "backend.md").read_text(
        encoding="utf-8"
    )
    assert stored == "new body"
    assert not (tmp_path / ".replacements").exists() or not list((tmp_path / ".replacements").glob("*"))


def test_atomic_artifact_replacement_can_roll_back_prior_file(tmp_path: Path) -> None:
    repository = FileSystemRenderingRepository(tmp_path)
    destination = tmp_path / "wiki" / "shared" / "interpretations" / "market_trend" / "backend.md"
    repository.write_artifact(
        {
            "domain": "recruiting",
            "layer": "interpretation",
            "record_id": "interp:1",
            "path": "wiki/shared/interpretations/market_trend/backend.md",
            "title": "Old page",
            "body_markdown": "old body",
            "scope_ref": {"scope": "shared"},
            "snapshot_ref": {"fact_snapshot_id": "fact_snap:1"},
        }
    )

    receipt = repository.replace_artifact_atomically(
        {
            "domain": "recruiting",
            "layer": "interpretation",
            "record_id": "interp:2",
            "path": "wiki/shared/interpretations/market_trend/backend.md",
            "title": "New page",
            "body_markdown": "new body",
            "scope_ref": {"scope": "shared"},
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:2",
                "interpretation_snapshot_id": "interp_snap:2",
            },
        }
    )
    repository.rollback_artifact_replacement(receipt)

    assert destination.read_text(encoding="utf-8") == "old body"
