# Both stages share the same base image so the virtualenv built in the builder
# keeps working when it is copied: a uv venv links back to the interpreter at a
# fixed path, which only holds if that path is identical in both stages.
FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Dependencies resolve from the lockfile alone, so this layer is reused on every
# build that does not touch pyproject.toml or uv.lock — editing a scraper no
# longer re-downloads the whole dependency tree.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . .

# Installs the project itself, which is what puts the nhl-* commands on PATH.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ---- Runtime stage ----
FROM python:3.13-slim-bookworm

# Needed for outbound HTTPS to the NHL, cbssports and capwages endpoints.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --create-home appuser

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app /app

# Puts the project's console scripts (nhl-daily-leaders, nhl-injuries, ...) first.
ENV PATH="/app/.venv/bin:$PATH"

USER appuser

# Every job is a one-shot command and the image has no default: scheduling lives
# on the host (see deploy/systemd/), which always names the job it wants. Running
# the image bare is a mistake, so say which one is missing and exit non-zero.
CMD ["sh", "-c", "echo 'nhl-helper: no job given, e.g. docker run --rm <image> nhl-injuries' >&2; exit 64"]
