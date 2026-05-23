#
# Production-oriented Dockerfile for FastAPI (Python 3.11)
# - Multi-stage build for smaller runtime image
# - Non-root user
# - Gunicorn + Uvicorn workers (better than bare uvicorn for prod)
#

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY requirements.txt .

# Build wheels to keep the runtime image slim and deterministic-ish.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/* && \
    python -m pip install --upgrade pip wheel && \
    python -m pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Create non-root user early so we can COPY --chown.
RUN adduser --disabled-password --gecos "" --home /app appuser

# Install runtime deps from wheels produced in the builder stage.
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

# Copy application code + Stitch landing page.
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser index.html ./index.html
COPY --chown=appuser:appuser gunicorn_conf.py ./gunicorn_conf.py
USER appuser

EXPOSE 8000

# Basic healthcheck (disabled by default on some platforms; safe if enabled).
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()" || exit 1

CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.main:app"]
