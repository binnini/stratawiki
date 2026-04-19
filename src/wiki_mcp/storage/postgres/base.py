from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Protocol, Sequence

from wiki_mcp.schemas.scope_ref import ScopeRef


class CursorLike(Protocol):
    def execute(self, query: str, params: Sequence[Any] | None = None) -> Any:
        ...

    def fetchone(self) -> Any:
        ...

    def fetchall(self) -> list[Any]:
        ...

    @property
    def rowcount(self) -> int:
        ...


class ConnectionLike(Protocol):
    def cursor(self) -> CursorLike:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


@contextmanager

def managed_cursor(connection: ConnectionLike) -> Iterator[CursorLike]:
    cursor = connection.cursor()
    try:
        yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise


class PostgresRepositoryBase:
    """Small helper base for DB-API compatible Postgres repositories.

    These repositories intentionally operate on envelope-style tables first.
    Domain-specific normalized fact tables can be introduced later behind the
    same service and repository contracts.
    """

    def __init__(self, connection: ConnectionLike) -> None:
        self.connection = connection

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _scope_filter_sql(
        self,
        scope_ref: ScopeRef,
        *,
        table_alias: str = "",
    ) -> tuple[str, list[Any]]:
        prefix = f"{table_alias}." if table_alias else ""
        scope = scope_ref["scope"]
        clauses = [f"{prefix}scope = %s"]
        params: list[Any] = [scope]

        if scope == "tenant":
            clauses.append(f"{prefix}tenant_id = %s")
            params.append(scope_ref.get("tenant_id"))
        elif scope == "user":
            clauses.append(f"{prefix}tenant_id = %s")
            clauses.append(f"{prefix}user_id = %s")
            params.append(scope_ref.get("tenant_id"))
            params.append(scope_ref.get("user_id"))

        return " AND ".join(clauses), params

    def _row_to_dict(self, row: Mapping[str, Any] | Any) -> dict[str, Any]:
        if isinstance(row, Mapping):
            return {
                str(key): self._normalize_db_value(value)
                for key, value in dict(row).items()
            }
        raise TypeError(
            "Repository rows must be mapping-like. Configure the Postgres driver "
            "with a dict or row-factory compatible cursor."
        )

    def _normalize_db_value(self, value: Any) -> Any:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, list):
            return [self._normalize_db_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._normalize_db_value(item) for item in value)
        if isinstance(value, dict):
            return {
                str(key): self._normalize_db_value(item)
                for key, item in value.items()
            }
        return value
