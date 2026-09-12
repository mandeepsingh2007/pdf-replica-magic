#!/bin/sh
set -e

BACKEND_DB="/app/backend/test_generator.db"
DEPLOY_DB="/app/backend/test_generator.db.deploy"

if [ ! -f "$BACKEND_DB" ] && [ -f "$DEPLOY_DB" ]; then
  cp "$DEPLOY_DB" "$BACKEND_DB"
  echo "Created $BACKEND_DB from deploy bundle"
fi

mkdir -p /data 2>/dev/null || true

if [ -f "$BACKEND_DB" ]; then
  if [ -d /data ] && [ -w /data ]; then
    cp -f "$BACKEND_DB" /data/test_generator.db
    export DATABASE_URL="sqlite+aiosqlite:////data/test_generator.db"
    echo "Using SQLite at /data/test_generator.db"
  else
    export DATABASE_URL="sqlite+aiosqlite:////app/backend/test_generator.db"
    echo "Using SQLite at /app/backend/test_generator.db (no writable /data)"
  fi
else
  echo "WARNING: No seed database in image — subjects API will be empty until seed_pdfs runs"
  export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:////data/test_generator.db}"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
