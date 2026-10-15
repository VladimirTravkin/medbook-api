#!/bin/sh
set -e

# Railway sets $PORT dynamically; fall back to 8000 for local runs
PORT="${PORT:-8000}"

echo "[entrypoint] running alembic migrations..."
alembic upgrade head

echo "[entrypoint] starting uvicorn on port ${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --app-dir src
