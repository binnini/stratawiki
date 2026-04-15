from __future__ import annotations

import os
from typing import Sequence

import psycopg
from psycopg.rows import dict_row

from wiki_mcp.adapters.sources.worknet import (
    WorknetRecruitingExternalAdapter,
    WorknetRecruitingSourceProvider,
)
from wiki_mcp.domains.recruiting import RecruitingSourceIngestionPlugin
from wiki_mcp.schemas.ingestion_execution_result import IngestionExecutionResult
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.services.core_ingestion import DefaultCoreIngestionService
from wiki_mcp.services.interfaces.core_ingestion import CoreIngestionService
from wiki_mcp.services.interfaces.domain_ingestion import DomainIngestionPlugin
from wiki_mcp.storage.postgres import (
    PostgresFactRepository,
    PostgresOutboxRepository,
    PostgresSnapshotRepository,
)


DEFAULT_DATABASE_URL = "postgresql://stratawiki:stratawiki@localhost:5432/stratawiki"


class DefaultIngestionEntrypoint:
    """Application-facing ingestion entrypoint for adapter-plus-core orchestration."""

    def __init__(
        self,
        *,
        core_ingestion_service: CoreIngestionService,
        plugins: Sequence[DomainIngestionPlugin],
        worknet_adapter: WorknetRecruitingExternalAdapter | None = None,
    ) -> None:
        self.core_ingestion_service = core_ingestion_service
        self.plugins = list(plugins)
        self.worknet_adapter = worknet_adapter or WorknetRecruitingExternalAdapter()

    def ingest_source(self, source: SourceRecord) -> IngestionExecutionResult:
        plugins = [plugin for plugin in self.plugins if plugin.accepts(source)]
        if not plugins:
            return {
                "ok": False,
                "source": source,
                "error": {
                    "code": "plugin_not_found",
                    "message": f"No ingestion plugin accepts source domain {source['domain']!r}.",
                    "details": {
                        "domain": source["domain"],
                        "connector": source["connector"],
                    },
                },
            }

        if len(plugins) > 1:
            return {
                "ok": False,
                "source": source,
                "error": {
                    "code": "plugin_ambiguous",
                    "message": f"Multiple ingestion plugins accept source domain {source['domain']!r}.",
                    "details": {
                        "domain": source["domain"],
                        "plugin_names": [plugin.__class__.__name__ for plugin in plugins],
                    },
                },
            }

        plugin = plugins[0]
        try:
            batch = self.core_ingestion_service.prepare_batch(source, plugin)
        except Exception as exc:
            return {
                "ok": False,
                "source": source,
                "plugin_name": plugin.__class__.__name__,
                "error": {
                    "code": "prepare_failed",
                    "message": str(exc),
                },
            }

        if not batch["validation"]["ok"]:
            return {
                "ok": False,
                "source": batch["source"],
                "plugin_name": plugin.__class__.__name__,
                "validation": batch["validation"],
                "error": {
                    "code": "validation_failed",
                    "message": "Ingestion batch validation failed.",
                    "details": {
                        "errors": batch["validation"]["errors"],
                        "warnings": batch["validation"]["warnings"],
                    },
                },
            }

        try:
            result = self.core_ingestion_service.ingest_batch(batch)
        except Exception as exc:
            return {
                "ok": False,
                "source": batch["source"],
                "plugin_name": plugin.__class__.__name__,
                "validation": batch["validation"],
                "error": {
                    "code": "ingest_failed",
                    "message": str(exc),
                },
            }

        return {
            "ok": True,
            "source": batch["source"],
            "plugin_name": plugin.__class__.__name__,
            "validation": batch["validation"],
            "ingestion_result": result,
        }

    def ingest_worknet_source(
        self,
        provider: WorknetRecruitingSourceProvider,
        source_id: str,
        *,
        auth_key: str | None = None,
        include_raw: bool = False,
    ) -> IngestionExecutionResult:
        try:
            source = self.worknet_adapter.fetch_source_record(
                provider,
                source_id,
                auth_key=auth_key,
                include_raw=include_raw,
            )
        except Exception as exc:
            return {
                "ok": False,
                "error": {
                    "code": "source_fetch_failed",
                    "message": str(exc),
                    "details": {
                        "connector": self.worknet_adapter.connector_name,
                        "source_id": source_id,
                    },
                },
            }

        return self.ingest_source(source)


def connect_postgres(database_url: str | None = None) -> psycopg.Connection[dict]:
    resolved_url = database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
    psycopg_url = resolved_url.replace("+psycopg", "", 1)
    return psycopg.connect(psycopg_url, row_factory=dict_row)


def build_default_ingestion_entrypoint(
    connection: psycopg.Connection[dict],
) -> DefaultIngestionEntrypoint:
    core_ingestion_service = DefaultCoreIngestionService(
        fact_repository=PostgresFactRepository(connection),
        snapshot_repository=PostgresSnapshotRepository(connection),
        outbox_repository=PostgresOutboxRepository(connection),
    )
    return DefaultIngestionEntrypoint(
        core_ingestion_service=core_ingestion_service,
        plugins=[RecruitingSourceIngestionPlugin()],
    )
