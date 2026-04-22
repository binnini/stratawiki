from __future__ import annotations

from wiki_mcp.personal_markdown_migration import (
    _infer_subspace,
    _legacy_storage,
    _normalize_string_list,
    _parse_legacy_personal_body,
    _positive_int,
    _pruned_provenance,
)


def test_infer_subspace_prefers_legacy_provenance_when_present() -> None:
    assert _infer_subspace(
        path="wiki/users/user-1/documents/raw/doc.md",
        provenance={"_personal_document": {"subspace": "wiki"}},
    ) == "wiki"


def test_infer_subspace_falls_back_to_path_convention() -> None:
    assert _infer_subspace(path="wiki/users/user-1/answers/saved.md", provenance={}) == "wiki"
    assert _infer_subspace(path="wiki/users/user-1/personal-documents/pdoc_1.md", provenance={}) == "raw"


def test_pruned_provenance_removes_internal_storage_key_when_requested() -> None:
    assert _pruned_provenance(
        {"generated_by": {"kind": "user"}, "_personal_document": {"subspace": "raw"}},
        prune_legacy_provenance=True,
    ) == {"generated_by": {"kind": "user"}}


def test_migration_helpers_normalize_legacy_values() -> None:
    assert _legacy_storage({"_personal_document": {"version": 3}}) == {"version": 3}
    assert _normalize_string_list(["asset:1", "", None, "asset:2"]) == ["asset:1", "asset:2"]
    assert _positive_int(0, default=7) == 7
    assert _positive_int(4, default=7) == 4


def test_legacy_body_parser_can_strip_personal_comment_metadata() -> None:
    metadata, body_markdown = _parse_legacy_personal_body(
        "<!-- stratawiki:personal_document {\"subspace\":\"raw\"} -->\n\n# Title\n\nBody.\n"
    )

    assert metadata == {"subspace": "raw"}
    assert body_markdown == "# Title\n\nBody."
