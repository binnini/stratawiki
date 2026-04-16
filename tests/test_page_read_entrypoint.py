from __future__ import annotations

from pathlib import Path

from psycopg import Connection

from wiki_mcp.services.page_read_entrypoint import (
    DefaultPageReadEntrypoint,
    build_default_page_read_entrypoint,
)


class StubPageReadService:
    def __init__(self) -> None:
        self.get_calls: list[dict[str, object]] = []
        self.list_calls: list[dict[str, object]] = []

    def get_page(self, **kwargs: object) -> dict[str, object] | None:
        self.get_calls.append(kwargs)
        if kwargs["record_id"] == "personal:plan-1":
            return {
                "domain": "recruiting",
                "layer": "personal",
                "record_id": "personal:plan-1",
                "path": "wiki/personal/tenant-1/user-1/plan-1.md",
                "title": "Backend transition plan",
                "scope_ref": {
                    "scope": "user",
                    "tenant_id": "tenant-1",
                    "user_id": "user-1",
                },
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:new",
                    "interpretation_snapshot_id": "interp_snap:new",
                    "profile_version": "profile-v2",
                },
                "metadata": {"title": "Backend transition plan"},
                "body_markdown": "# Backend transition plan\n",
            }
        return None

    def list_pages(self, **kwargs: object) -> list[dict[str, object]]:
        self.list_calls.append(kwargs)
        return [
            {
                "domain": "recruiting",
                "layer": "personal",
                "record_id": "personal:plan-1",
                "path": "wiki/personal/tenant-1/user-1/plan-1.md",
                "title": "Backend transition plan",
                "scope_ref": {
                    "scope": "user",
                    "tenant_id": "tenant-1",
                    "user_id": "user-1",
                },
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:new",
                    "interpretation_snapshot_id": "interp_snap:new",
                    "profile_version": "profile-v2",
                },
                "metadata": {"title": "Backend transition plan"},
            }
        ]


def test_page_read_entrypoint_returns_personal_page() -> None:
    entrypoint = DefaultPageReadEntrypoint(page_read_service=StubPageReadService())

    result = entrypoint.get_personal_page(
        domain="recruiting",
        tenant_id="tenant-1",
        user_id="user-1",
        record_id="personal:plan-1",
    )

    assert result["ok"] is True
    assert result["read_model_state"] == "applied"
    assert result["page"]["record_id"] == "personal:plan-1"


def test_page_read_entrypoint_returns_not_found_error() -> None:
    entrypoint = DefaultPageReadEntrypoint(page_read_service=StubPageReadService())

    result = entrypoint.get_personal_page(
        domain="recruiting",
        tenant_id="tenant-1",
        user_id="user-1",
        record_id="personal:missing",
    )

    assert result == {
        "ok": False,
        "read_model_state": "not_applicable",
        "error": {
            "code": "page_not_found",
            "message": "No rendered page matched the requested domain/layer/record scope.",
            "details": {
                "domain": "recruiting",
                "layer": "personal",
                "record_id": "personal:missing",
                "scope": "user",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
            },
        },
    }


def test_page_read_entrypoint_lists_personal_pages() -> None:
    entrypoint = DefaultPageReadEntrypoint(page_read_service=StubPageReadService())

    result = entrypoint.list_personal_pages(
        domain="recruiting",
        tenant_id="tenant-1",
        user_id="user-1",
        limit=5,
    )

    assert result["ok"] is True
    assert result["read_model_state"] == "applied"
    assert [page["record_id"] for page in result["pages"]] == ["personal:plan-1"]


def test_page_read_entrypoint_returns_interpretation_page() -> None:
    entrypoint = DefaultPageReadEntrypoint(page_read_service=StubPageReadService())

    result = entrypoint.get_interpretation_page(
        domain="recruiting",
        record_id="personal:plan-1",
    )

    assert result["ok"] is True
    assert result["read_model_state"] == "applied"
    assert result["page"]["record_id"] == "personal:plan-1"


def test_page_read_entrypoint_lists_interpretation_pages() -> None:
    entrypoint = DefaultPageReadEntrypoint(page_read_service=StubPageReadService())

    result = entrypoint.list_interpretation_pages(
        domain="recruiting",
        limit=5,
    )

    assert result["ok"] is True
    assert result["read_model_state"] == "applied"
    assert [page["record_id"] for page in result["pages"]] == ["personal:plan-1"]


def test_default_page_read_entrypoint_loads_personal_page_from_postgres_and_filesystem(
    postgres_connection: Connection[dict],
    tmp_path: Path,
) -> None:
    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO graph.rendered_page (
                domain,
                layer,
                record_id,
                path,
                scope,
                tenant_id,
                user_id,
                fact_snapshot_id,
                interpretation_snapshot_id,
                profile_version,
                metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                "recruiting",
                "personal",
                "personal:plan-1",
                "wiki/personal/tenant-1/user-1/plan-1.md",
                "user",
                "tenant-1",
                "user-1",
                "fact_snap:new",
                "interp_snap:new",
                "profile-v2",
                '{"title": "Backend transition plan"}',
            ),
        )
    postgres_connection.commit()
    stored_path = tmp_path / "wiki/personal/tenant-1/user-1/plan-1.md"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_text("# Backend transition plan\n", encoding="utf-8")

    entrypoint = build_default_page_read_entrypoint(
        postgres_connection,
        render_root=tmp_path,
    )

    result = entrypoint.get_personal_page(
        domain="recruiting",
        tenant_id="tenant-1",
        user_id="user-1",
        record_id="personal:plan-1",
    )

    assert result == {
        "ok": True,
        "read_model_state": "applied",
        "page": {
            "domain": "recruiting",
            "layer": "personal",
            "record_id": "personal:plan-1",
            "path": "wiki/personal/tenant-1/user-1/plan-1.md",
            "title": "Backend transition plan",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:new",
                "interpretation_snapshot_id": "interp_snap:new",
                "profile_version": "profile-v2",
            },
            "metadata": {"title": "Backend transition plan"},
            "body_markdown": "# Backend transition plan\n",
        },
    }
