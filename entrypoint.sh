#!/bin/sh
set -e

# Run idempotent schema setup on every startup.
# - init_db creates any missing tables
# - migrations add columns if they don't already exist
echo "[entrypoint] running schema setup..."
uv run python scripts/init_db.py
uv run python scripts/migrate_add_embeddings.py
uv run python scripts/migrate_add_canonical_id.py

# If a command was passed (e.g. "python scripts/save_one.py"), run it.
# Otherwise default: start the FastAPI server.
if [ "$#" -eq 0 ]; then
    echo "[entrypoint] starting uvicorn..."
    exec uv run uvicorn applytrak.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/src
else
    echo "[entrypoint] running custom command: $*"
    exec uv run "$@"
fi
