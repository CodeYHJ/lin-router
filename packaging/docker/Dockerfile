# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS dependencies

WORKDIR /app
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY requirements/server.txt /tmp/requirements/server.txt
RUN python -m venv /app/.venv \
    && /app/.venv/bin/python -m pip install --no-cache-dir --upgrade pip \
    && /app/.venv/bin/python -m pip install --no-cache-dir -r /tmp/requirements/server.txt

FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LINROUTER_HOST=0.0.0.0 \
    LINROUTER_PORT=18400 \
    LINROUTER_CONFIG=/data/lin-router-config.json

WORKDIR /app

RUN groupadd --system --gid 10001 linrouter \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --no-create-home linrouter \
    && mkdir -p /data \
    && chown -R linrouter:linrouter /data /app

COPY --from=dependencies /app/.venv /app/.venv
COPY linrouter_core/ /app/linrouter_core/
COPY linrouter_server/ /app/linrouter_server/
COPY web/shared/ /app/static/
COPY packaging/docker/entrypoint.sh /app/entrypoint.sh

RUN chmod 0755 /app/entrypoint.sh \
    && chown -R linrouter:linrouter /app

USER linrouter
EXPOSE 18400
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('LINROUTER_PORT', '18400') + '/health', timeout=3)"]

ENTRYPOINT ["/app/entrypoint.sh"]
