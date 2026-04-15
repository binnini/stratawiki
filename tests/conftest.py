from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki"


def _psycopg_connect_url(database_url: str) -> str:
    return database_url.replace("+psycopg", "", 1)


def _alembic_database_url(database_url: str) -> str:
    if "+psycopg" in database_url:
        return database_url
    return database_url.replace("postgresql://", "postgresql+psycopg://", 1)


def _connect(database_url: str) -> psycopg.Connection[dict]:
    return psycopg.connect(_psycopg_connect_url(database_url), row_factory=dict_row)


def _truncate_all(connection: psycopg.Connection[dict]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE
                graph.rendered_page,
                graph.dependency_edge,
                ops.outbox_event,
                ops.snapshot_publication,
                ops.snapshot_pointer,
                personal.profile_context,
                personal.record,
                interp.record,
                fact.relation_envelopes,
                fact.record_envelopes
            RESTART IDENTITY CASCADE
            """
        )
    connection.commit()


@pytest.fixture(scope="session")
def postgres_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


@pytest.fixture(scope="session")
def bootstrapped_postgres(postgres_database_url: str) -> str:
    try:
        connection = _connect(postgres_database_url)
    except psycopg.Error as exc:
        pytest.skip(f"Postgres integration tests require a reachable DATABASE_URL: {exc}")
    else:
        connection.close()

    env = os.environ.copy()
    env["DATABASE_URL"] = _alembic_database_url(postgres_database_url)
    subprocess.run(
        ["python3", "-m", "alembic", "upgrade", "head"],
        cwd=ROOT_DIR,
        env=env,
        check=True,
    )
    return postgres_database_url


@pytest.fixture
def postgres_connection(bootstrapped_postgres: str) -> psycopg.Connection[dict]:
    connection = _connect(bootstrapped_postgres)
    _truncate_all(connection)
    try:
        yield connection
    finally:
        _truncate_all(connection)
        connection.close()
