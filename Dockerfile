# syntax=docker/dockerfile:1

# ---- Build stage -------------------------------------------------------
# Dependencies are resolved and installed here. Nothing from this stage
# reaches the final image except the finished virtualenv.
FROM python:3.13-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy only the dependency manifests first. This layer is cached and rebuilt
# solely when dependencies change -- editing app.py will not reinstall FastAPI.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Now the source, and install the project itself. --no-editable installs a real
# wheel rather than a path link, so the runtime image needs no source tree.
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---- Runtime stage -----------------------------------------------------
# A clean image: no uv, no compilers, no lockfile, no build caches.
FROM python:3.13-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RUNFUEL_DB_PATH=/data/runfuel.db

# Run as an unprivileged user. Ownership alone is not enough -- USER below is
# what actually drops privileges.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

USER appuser

# SQLite lives here. Mount something at /data or the log dies with the container.
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request as u, sys; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"

# 0.0.0.0, not the uvicorn default of 127.0.0.1: inside a container the default
# means "reachable only from within this container", and publishing the port
# would silently give you nothing.
CMD ["uvicorn", "runfuel.app:app", "--host", "0.0.0.0", "--port", "8000"]
