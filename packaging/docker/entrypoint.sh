#!/bin/sh
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec /app/.venv/bin/python -m linrouter_server \
  --host "${LINROUTER_HOST:-0.0.0.0}" \
  --port "${LINROUTER_PORT:-18400}" \
  --config "${LINROUTER_CONFIG:-/data/lin-router-config.json}"
