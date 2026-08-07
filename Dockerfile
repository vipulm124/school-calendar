FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app

WORKDIR /app

# Runtime + build deps:
# - libpq / gcc: psycopg2
# - libheif: pillow-heif (iPhone HEIC)
# - curl: healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        libheif1 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv

# Install dependencies from the lockfile without installing this repo as a package
# (pyproject has no [build-system] / package layout).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# FastAPI app lives in packages/server/app and uses absolute imports (api, core, ...)
COPY packages/server/app/ ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# App has no "/" route; /docs is always available from FastAPI.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/docs" >/dev/null || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
