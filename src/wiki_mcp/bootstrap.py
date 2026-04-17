from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import psycopg


DEFAULT_DATABASE_URL = "postgresql://stratawiki:stratawiki@localhost:5432/stratawiki"


@dataclass(slots=True)
class BootstrapContext:
    """Minimal runtime bootstrap context for the current migration stage.

    The implementation intentionally keeps bootstrap narrow until the new
    retrieval, orchestration, and tool layers are rebuilt around the current
    docs-defined architecture.
    """

    connection: Any
    owns_connection: bool = False

    def close(self) -> None:
        if self.owns_connection and not self.connection.closed:
            self.connection.close()


def resolve_database_url(database_url: str | None = None) -> str:
    return database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def connect_postgres(database_url: str | None = None) -> Any:
    import psycopg
    from psycopg.rows import dict_row

    resolved_url = resolve_database_url(database_url)
    psycopg_url = resolved_url.replace("+psycopg", "", 1)
    return psycopg.connect(psycopg_url, row_factory=dict_row)


def bootstrap_application(
    *,
    connection: Any | None = None,
    database_url: str | None = None,
) -> BootstrapContext:
    owns_connection = connection is None
    resolved_connection = connection or connect_postgres(database_url)
    return BootstrapContext(
        connection=resolved_connection,
        owns_connection=owns_connection,
    )
