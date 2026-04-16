from __future__ import annotations

from wiki_mcp.services.page_reads import DefaultPageReadService


class StubRenderingRepository:
    def __init__(self) -> None:
        self.get_calls: list[dict[str, object]] = []
        self.list_calls: list[dict[str, object]] = []

    def write_artifact(self, artifact: dict[str, object]) -> str:
        raise AssertionError("write_artifact should not be called in page read tests")

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


def test_page_read_service_gets_rendered_page() -> None:
    rendering_repository = StubRenderingRepository()
    service = DefaultPageReadService(rendering_repository=rendering_repository)

    page = service.get_page(
        domain="recruiting",
        layer="personal",
        record_id="personal:plan-1",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert page is not None
    assert page["title"] == "Backend transition plan"
    assert page["body_markdown"] == "# Backend transition plan\n"
    assert rendering_repository.get_calls == [
        {
            "domain": "recruiting",
            "layer": "personal",
            "record_id": "personal:plan-1",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        }
    ]


def test_page_read_service_lists_pages_for_scope() -> None:
    rendering_repository = StubRenderingRepository()
    service = DefaultPageReadService(rendering_repository=rendering_repository)

    pages = service.list_pages(
        domain="recruiting",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        layer="personal",
        limit=5,
    )

    assert [page["record_id"] for page in pages] == ["personal:plan-1"]
    assert rendering_repository.list_calls == [
        {
            "domain": "recruiting",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
            "layer": "personal",
            "limit": 5,
        }
    ]
