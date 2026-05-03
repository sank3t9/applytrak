# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install uv (fast Python package manager) by copying its binary from astral's image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# --- Layer 1: install dependencies ------------------------------------------
# Cache-friendly: only invalidates when pyproject.toml or uv.lock changes.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# --- Layer 2: install the project itself ------------------------------------
COPY src ./src
COPY scripts ./scripts
COPY entrypoint.sh ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen \
    && chmod +x ./entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
