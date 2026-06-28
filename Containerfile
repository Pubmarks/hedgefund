ARG BASE=ghcr.io/astral-sh/uv:python3.13-bookworm-slim@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca

# ----------------------------------------------------------------------------
# Stage 1: builder — install the locked dependency set into /app/.venv
# ----------------------------------------------------------------------------
FROM ${BASE} AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Cache layer keyed on the lock files only; the app code is copied later.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ----------------------------------------------------------------------------
# Stage 2: runtime — same base, minus build caches; only venv + app + uv
# ----------------------------------------------------------------------------
FROM ${BASE} AS runtime

LABEL org.opencontainers.image.title="main" \
      org.opencontainers.image.description="Claude Agent SDK WebFetch example" \
      org.opencontainers.image.source="https://github.com/anthropics/claude-agent-sdk-python"

# Unprivileged user with a writable HOME (the bundled Claude CLI needs one).
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app app

ENV PATH="/app/.venv/bin:$PATH" \
    HOME="/home/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_SYNC=1 \
    UV_FROZEN=1 \
    UV_NO_CACHE=1

WORKDIR /app

# Pre-built virtual environment and project metadata from the builder stage.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app pyproject.toml uv.lock main.py config.py ./

USER app

STOPSIGNAL SIGINT

ENTRYPOINT ["uv", "run", "--frozen", "--no-sync", "python", "main.py"]
