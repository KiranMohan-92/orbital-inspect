#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
FRONTEND_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
BACKEND_DIR=$(cd -- "$FRONTEND_DIR/../backend" && pwd)

export PYTHONPATH=.
export GEMINI_API_KEY="${GEMINI_API_KEY:-test-dummy-key}"
export DEMO_MODE="${DEMO_MODE:-true}"
export E2E_TEST_MODE="${E2E_TEST_MODE:-true}"
export DATA_DIR="${ORBITAL_INSPECT_E2E_ROOT:-/tmp/orbital_inspect_e2e}"
export UPLOADS_DIR="${ORBITAL_INSPECT_E2E_UPLOADS_PATH:-${DATA_DIR}/uploads}"
export DEMO_CACHE_DIR="${ORBITAL_INSPECT_E2E_DEMO_CACHE_DIR:-${DATA_DIR}/demo_cache}"
export DEMO_IMAGES_DIR="${ORBITAL_INSPECT_E2E_DEMO_IMAGES_DIR:-${BACKEND_DIR}/data/demo_images}"
export DATABASE_URL="${ORBITAL_INSPECT_E2E_DATABASE_URL:-sqlite+aiosqlite:///file:orbital_inspect_e2e?mode=memory&cache=shared&uri=true}"

cd "$BACKEND_DIR"
exec python -m uvicorn main:app --host 127.0.0.1 --port "${ORBITAL_INSPECT_E2E_BACKEND_PORT:-8000}"
