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

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Cache layer keyed on the lock files only; the app code is copied later.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ----------------------------------------------------------------------------
# Stage 2: runtime — same base, minus build caches; only venv + app + uv
# ----------------------------------------------------------------------------
FROM ${BASE} AS runtime

LABEL org.opencontainers.image.title="hedgefund" \
      org.opencontainers.image.description="Agentic hedge fund research agents" \
      org.opencontainers.image.source="https://github.com/Pubmarks/hedgefund"

# Unprivileged user with a writable HOME (OpenCode stores local state there).
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app app \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates tar \
    && rm -rf /var/lib/apt/lists/* \
    && ARCH="$(uname -m | sed 's/x86_64/x64/;s/aarch64/arm64/')" \
    && curl -fsSL "https://github.com/anomalyco/opencode/releases/latest/download/opencode-linux-${ARCH}.tar.gz" \
      | tar -xz -C /usr/local/bin opencode \
    && chmod 755 /usr/local/bin/opencode \
    && opencode --version

ENV PATH="/app/.venv/bin:/usr/local/bin:$PATH" \
    HOME="/home/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_SYNC=1 \
    UV_FROZEN=1 \
    UV_NO_CACHE=1 \
    OPENCODE_DISABLE_DEFAULT_PLUGINS=1 \
    OPENCODE_PURE=1

WORKDIR /app

# Pre-built virtual environment and project metadata from the builder stage.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app pyproject.toml uv.lock opencode.json ./
COPY --chown=app:app main.py config.py agent.py pipeline.py ./
COPY --chown=app:app agents/ agents/
COPY --chown=app:app phases/ phases/
COPY --chown=app:app memory/ memory/
RUN mkdir -p /app/out && chown app:app /app/out

USER app

STOPSIGNAL SIGINT

ENTRYPOINT ["uv", "run", "--frozen", "--no-sync", "python", "main.py"]
