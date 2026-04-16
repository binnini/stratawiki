from __future__ import annotations

from pathlib import Path

from psycopg import Connection

from wiki_mcp.schemas.page_list_result import PageListResult
from wiki_mcp.schemas.page_read_result import PageReadResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.services.page_reads import DefaultPageReadService
from wiki_mcp.storage.filesystem.rendering import (
    FilesystemAndPostgresRenderingRepository,
)


DEFAULT_RENDER_ROOT = Path("data")


class DefaultPageReadEntrypoint:
    """Application-facing read authority for rendered page retrieval."""

    def __init__(
        self,
        *,
        page_read_service: DefaultPageReadService,
    ) -> None:
        self.page_read_service = page_read_service

    def get_page(
        self,
        *,
        domain: str,
        layer: str,
        record_id: str,
        scope_ref: ScopeRef,
    ) -> PageReadResult:
        page = self.page_read_service.get_page(
            domain=domain,
            layer=layer,
            record_id=record_id,
            scope_ref=scope_ref,
        )
        if page is None:
            return {
                "ok": False,
                "read_model_state": "not_applicable",
                "error": {
                    "code": "page_not_found",
                    "message": "No rendered page matched the requested domain/layer/record scope.",
                    "details": {
                        "domain": domain,
                        "layer": layer,
                        "record_id": record_id,
                        "scope": scope_ref["scope"],
                        **(
                            {"tenant_id": scope_ref["tenant_id"]}
                            if "tenant_id" in scope_ref
                            else {}
                        ),
                        **(
                            {"user_id": scope_ref["user_id"]}
                            if "user_id" in scope_ref
                            else {}
                        ),
                    },
                },
            }

        return {
            "ok": True,
            "read_model_state": "applied",
            "page": page,
        }

    def list_pages(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        layer: str | None = None,
        limit: int = 20,
    ) -> PageListResult:
        pages = self.page_read_service.list_pages(
            domain=domain,
            scope_ref=scope_ref,
            layer=layer,
            limit=limit,
        )
        return {
            "ok": True,
            "read_model_state": "applied",
            "pages": pages,
        }

    def get_personal_page(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        record_id: str,
    ) -> PageReadResult:
        return self.get_page(
            domain=domain,
            layer="personal",
            record_id=record_id,
            scope_ref={
                "scope": "user",
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
        )

    def list_personal_pages(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        limit: int = 20,
    ) -> PageListResult:
        return self.list_pages(
            domain=domain,
            scope_ref={
                "scope": "user",
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
            layer="personal",
            limit=limit,
        )

    def get_interpretation_page(
        self,
        *,
        domain: str,
        record_id: str,
    ) -> PageReadResult:
        return self.get_page(
            domain=domain,
            layer="interpretation",
            record_id=record_id,
            scope_ref={"scope": "shared"},
        )

    def list_interpretation_pages(
        self,
        *,
        domain: str,
        limit: int = 20,
    ) -> PageListResult:
        return self.list_pages(
            domain=domain,
            scope_ref={"scope": "shared"},
            layer="interpretation",
            limit=limit,
        )


def build_default_page_read_entrypoint(
    connection: Connection[dict],
    *,
    render_root: str | Path = DEFAULT_RENDER_ROOT,
) -> DefaultPageReadEntrypoint:
    page_read_service = DefaultPageReadService(
        rendering_repository=FilesystemAndPostgresRenderingRepository(
            render_root,
            connection,
        )
    )
    return DefaultPageReadEntrypoint(page_read_service=page_read_service)
