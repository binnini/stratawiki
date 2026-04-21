from __future__ import annotations

from pathlib import Path

from wiki_mcp.services.domain_pack_artifacts import (
    resolve_active_domain_pack_versions,
    resolve_domain_pack_paths,
)


def test_resolve_domain_pack_paths_accepts_jobs_wiki_alias_env(monkeypatch, tmp_path: Path) -> None:
    pack_path = tmp_path / "recruiting.json"
    pack_path.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("STRATAWIKI_DOMAIN_PACK_PATHS", raising=False)
    monkeypatch.setenv("JOBS_WIKI_STRATAWIKI_DOMAIN_PACK_PATHS", str(pack_path))

    resolved = resolve_domain_pack_paths()

    assert resolved == [pack_path.resolve()]


def test_resolve_active_domain_pack_versions_accepts_jobs_wiki_alias_env(
    monkeypatch,
) -> None:
    monkeypatch.delenv("STRATAWIKI_ACTIVE_DOMAIN_PACKS", raising=False)
    monkeypatch.setenv(
        "JOBS_WIKI_STRATAWIKI_ACTIVE_DOMAIN_PACKS",
        "recruiting=2026-04-18",
    )

    resolved = resolve_active_domain_pack_versions()

    assert resolved == {"recruiting": "2026-04-18"}
