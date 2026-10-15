# ============================================
# Stage 1: builder — install dependencies
# ============================================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies only (no project itself yet)
RUN uv sync --frozen --no-install-project --no-dev

# Copy source
COPY src ./src
COPY README.md README.ru.md ./

# Install project itself
RUN uv sync --frozen --no-dev

# ============================================
# Stage 2: runtime — slim image
# ============================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Copy virtualenv and source from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/pyproject.toml /app/uv.lock /app/

# Copy Alembic config and migrations
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./

# Copy entrypoint script
COPY --chown=app:app docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

USER app

# Railway provides $PORT at runtime; default to 8000 for local docker-compose
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
