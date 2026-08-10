#!/bin/sh
set -e

# Idempotent schema setup on every startup: creates missing tables, then adds
# any missing columns.
echo "[entrypoint] running schema setup..."
uv run python scripts/apply_schema.py

# If a command was passed (e.g. "python scripts/save_one.py"), run it.
# Otherwise default: start the FastAPI server.
if [ "$#" -eq 0 ]; then
    echo "[entrypoint] starting uvicorn..."
    exec uv run uvicorn applytrak.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/src
else
    echo "[entrypoint] running custom command: $*"
    exec uv run "$@"
fi
