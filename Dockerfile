FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app
# Even plain `docker run` must fail closed without a configured API token.
ENV SENTINEL_ENV=production PYTHONDONTWRITEBYTECODE=1
# Use an unprivileged user; keep the SQLite data directory writable.
RUN useradd --system --uid 10001 --home-dir /app --no-create-home atlas \
    && mkdir -p /app/.data \
    && chown -R atlas:atlas /app
USER atlas
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "from http.client import HTTPConnection; c = HTTPConnection('127.0.0.1', 8000, timeout=2); c.request('GET', '/api/health'); raise SystemExit(c.getresponse().status != 200)"]
# 0.0.0.0 is inside the container only. Compose publishes to 127.0.0.1.
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--ws-max-size", "16384", "--ws-max-queue", "4"]
