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
RUN python -m pip install --upgrade pip wheel && \
    python -m pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime deps from wheels produced in the builder stage.
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

# Copy application code + Stitch landing page.
COPY app ./app
COPY index.html ./index.html
COPY scripts ./scripts

# Create non-root user.
RUN adduser --disabled-password --gecos "" --home /app appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Basic healthcheck (disabled by default on some platforms; safe if enabled).
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/').read()" || exit 1

# Configure workers via env if desired.
# Example: WEB_CONCURRENCY=2
ENV WEB_CONCURRENCY=2

CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:8000 app.main:app"]

