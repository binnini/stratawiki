#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki}"
export STRATAWIKI_DB_READY_TIMEOUT="${STRATAWIKI_DB_READY_TIMEOUT:-60}"
POSTGRES_CONTAINER_NAME="${STRATAWIKI_DB_CONTAINER_NAME:-stratawiki-postgres}"

if docker container inspect "$POSTGRES_CONTAINER_NAME" >/dev/null 2>&1; then
  docker start "$POSTGRES_CONTAINER_NAME" >/dev/null 2>&1 || true
else
  docker compose up -d postgres
fi

python3 - <<'PY'
import os
import time

import psycopg


database_url = os.environ["DATABASE_URL"].replace("+psycopg", "", 1)
deadline = time.monotonic() + float(os.environ["STRATAWIKI_DB_READY_TIMEOUT"])
last_error = None

while time.monotonic() < deadline:
    try:
        with psycopg.connect(database_url):
            break
    except psycopg.Error as exc:
        last_error = exc
        time.sleep(1)
else:
    raise SystemExit(
        "Postgres did not become reachable within "
        f"{os.environ['STRATAWIKI_DB_READY_TIMEOUT']} seconds: {last_error}"
    )
PY

"$ROOT_DIR/scripts/db_upgrade.sh"

echo "StrataWiki PostgreSQL bootstrap completed against ${DATABASE_URL}"
