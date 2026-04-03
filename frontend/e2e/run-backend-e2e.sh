#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
FRONTEND_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
BACKEND_DIR=$(cd -- "$FRONTEND_DIR/../backend" && pwd)

export PYTHONPATH=.
export GEMINI_API_KEY="${GEMINI_API_KEY:-test-dummy-key}"
export DEMO_MODE="${DEMO_MODE:-false}"
export AUTH_ENABLED="${AUTH_ENABLED:-false}"
export E2E_TEST_MODE="${E2E_TEST_MODE:-true}"
export DATABASE_AUTO_INIT="${ORBITAL_INSPECT_E2E_DATABASE_AUTO_INIT:-true}"
export DATA_DIR="${ORBITAL_INSPECT_E2E_ROOT:-/tmp/orbital_inspect_e2e}"
export DEMO_CACHE_DIR="${ORBITAL_INSPECT_E2E_DEMO_CACHE_DIR:-${DATA_DIR}/demo_cache}"
export DEMO_IMAGES_DIR="${ORBITAL_INSPECT_E2E_DEMO_IMAGES_DIR:-${BACKEND_DIR}/data/demo_images}"
export DATABASE_URL="${ORBITAL_INSPECT_E2E_DATABASE_URL:-sqlite+aiosqlite:///file:orbital_inspect_e2e?mode=memory&cache=shared&uri=true}"
export STORAGE_BACKEND="${ORBITAL_INSPECT_E2E_STORAGE_BACKEND:-local}"
export STORAGE_LOCAL_ROOT="${ORBITAL_INSPECT_E2E_STORAGE_ROOT:-${DATA_DIR}/storage}"
export STORAGE_BUCKET="${ORBITAL_INSPECT_E2E_STORAGE_BUCKET:-orbital-inspect-e2e}"
export STORAGE_REGION="${ORBITAL_INSPECT_E2E_STORAGE_REGION:-us-east-1}"
export STORAGE_ENDPOINT_URL="${ORBITAL_INSPECT_E2E_STORAGE_ENDPOINT_URL:-}"
export STORAGE_ACCESS_KEY_ID="${ORBITAL_INSPECT_E2E_STORAGE_ACCESS_KEY_ID:-}"
export STORAGE_SECRET_ACCESS_KEY="${ORBITAL_INSPECT_E2E_STORAGE_SECRET_ACCESS_KEY:-}"
export STORAGE_PREFIX="${ORBITAL_INSPECT_E2E_STORAGE_PREFIX:-e2e}"
export STORAGE_FORCE_PATH_STYLE="${ORBITAL_INSPECT_E2E_STORAGE_FORCE_PATH_STYLE:-true}"
export STORAGE_CREATE_BUCKET="${ORBITAL_INSPECT_E2E_STORAGE_CREATE_BUCKET:-false}"

if [[ "$DATABASE_URL" == postgres* ]]; then
  python - <<'PY'
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def wait_for_database() -> None:
    database_url = os.environ["DATABASE_URL"]
    for _ in range(60):
        try:
            engine = create_async_engine(database_url)
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return
        except Exception:
            await asyncio.sleep(1)
    raise SystemExit("Database did not become ready in time")


asyncio.run(wait_for_database())
PY
fi

cd "$BACKEND_DIR"
exec python -m uvicorn main:app --host 127.0.0.1 --port "${ORBITAL_INSPECT_E2E_BACKEND_PORT:-8000}"
