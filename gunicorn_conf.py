import multiprocessing
import os


bind = os.getenv("BIND", "0.0.0.0:8000")
# Default to 1 worker to avoid memory blowups on small instances; override via WEB_CONCURRENCY.
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
worker_class = "uvicorn.workers.UvicornWorker"

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
loglevel = os.getenv("LOG_LEVEL", "info")

max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "0")) or 0
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "0")) or 0

accesslog = "-"
errorlog = "-"
