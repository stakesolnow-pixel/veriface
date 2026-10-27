#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -d "$ROOT/backend/.venv" ]]; then
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/pip" install -r "$ROOT/backend/requirements.txt"
fi

if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  (cd "$ROOT/frontend" && npm install)
fi

cleanup() {
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT

"$ROOT/backend/.venv/bin/uvicorn" app.main:app --reload --host 127.0.0.1 --port 8000 \
  --app-dir "$ROOT/backend" &
(cd "$ROOT/frontend" && npm run dev -- --host 127.0.0.1 --port 5173) &
wait
