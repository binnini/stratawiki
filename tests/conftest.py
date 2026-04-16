from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki"
AUTO_BOOTSTRAP_ENV_VAR = "STRATAWIKI_PG_AUTO_BOOTSTRAP"


def _psycopg_connect_url(database_url: str) -> str:
    return database_url.replace("+psycopg", "", 1)


def _alembic_database_url(database_url: str) -> str:
    if "+psycopg" in database_url:
        return database_url
    return database_url.replace("postgresql://", "postgresql+psycopg://", 1)


def _connect(database_url: str) -> psycopg.Connection[dict]:
    return psycopg.connect(_psycopg_connect_url(database_url), row_factory=dict_row)


def _can_connect(database_url: str) -> bool:
    try:
        connection = _connect(database_url)
    except psycopg.Error:
        return False
    else:
        connection.close()
        return True


def _run_db_script(script_name: str, database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = _alembic_database_url(database_url)
    subprocess.run(
        ["bash", str(ROOT_DIR / "scripts" / script_name)],
        cwd=ROOT_DIR,
        env=env,
        check=True,
    )


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
    database_url_from_env = os.environ.get("DATABASE_URL")
    auto_bootstrap_enabled = os.environ.get(AUTO_BOOTSTRAP_ENV_VAR, "1") != "0"
    database_was_bootstrapped = False

    if not _can_connect(postgres_database_url):
        should_auto_bootstrap = (
            auto_bootstrap_enabled
            and (
                database_url_from_env is None
                or postgres_database_url == DEFAULT_DATABASE_URL
            )
        )
        if should_auto_bootstrap:
            try:
                _run_db_script("bootstrap_db.sh", postgres_database_url)
                database_was_bootstrapped = True
            except subprocess.CalledProcessError as exc:
                pytest.skip(
                    "Postgres integration tests could not auto-bootstrap the "
                    "default local database. Ensure Docker is available or set "
                    f"{AUTO_BOOTSTRAP_ENV_VAR}=0 to skip. Script failed with "
                    f"exit code {exc.returncode}."
                )
        else:
            pytest.skip(
                "Postgres integration tests require a reachable DATABASE_URL. "
                f"Current value: {postgres_database_url}"
            )

    if not _can_connect(postgres_database_url):
        pytest.skip(
            "Postgres integration tests require a reachable DATABASE_URL even "
            f"after bootstrap: {postgres_database_url}"
        )

    if not database_was_bootstrapped:
        _run_db_script("db_upgrade.sh", postgres_database_url)
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
