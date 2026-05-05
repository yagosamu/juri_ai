#!/usr/bin/env bash
set -o errexit

if [ -n "$GOOGLE_CLIENT_SECRET_JSON" ] && [ -n "$GOOGLE_CLIENT_SECRET_PATH" ]; then
  mkdir -p "$(dirname "$GOOGLE_CLIENT_SECRET_PATH")"
  printf '%s' "$GOOGLE_CLIENT_SECRET_JSON" > "$GOOGLE_CLIENT_SECRET_PATH"
fi

mkdir -p "${DATA_DIR:-/tmp/juri-ai}/media" "${DATA_DIR:-/tmp/juri-ai}/lancedb"

python -m gunicorn core.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
