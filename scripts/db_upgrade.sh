#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki}"

python3 -m alembic upgrade head
