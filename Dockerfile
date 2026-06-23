# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS base

# System deps for sentence-transformers / torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (matches our local toolchain)
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install deps into a project-local venv
RUN uv sync --frozen --no-install-project

# Copy source and finish install
COPY src ./src
COPY scripts ./scripts
RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]