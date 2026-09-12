#!/bin/sh
set -e
mkdir -p /data

if [ ! -f /data/test_generator.db ] && [ -f /app/backend/test_generator.db ]; then
  cp /app/backend/test_generator.db /data/test_generator.db
  echo "Copied seed database to /data/test_generator.db"
fi

export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:////data/test_generator.db}"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
