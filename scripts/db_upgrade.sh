#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki}"

python3 - <<'PY'
import os

import psycopg


database_url = os.environ["DATABASE_URL"].replace("+psycopg", "", 1)

try:
    with psycopg.connect(database_url):
        pass
except psycopg.Error as exc:
    raise SystemExit(
        "DATABASE_URL is not reachable for Alembic upgrade. "
        "Run scripts/bootstrap_db.sh for the default local Postgres or point "
        f"DATABASE_URL at a reachable database. Original error: {exc}"
    )
PY

python3 -m alembic upgrade head

echo "Alembic upgrade completed against ${DATABASE_URL}"
