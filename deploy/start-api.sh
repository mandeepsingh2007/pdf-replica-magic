#!/bin/sh
set -e

BACKEND_DB="/app/backend/test_generator.db"
DEPLOY_DB="/app/backend/test_generator.db.deploy"
TARGET="/data/test_generator.db"
MIN_SEED_BYTES=50000

if [ ! -f "$BACKEND_DB" ] && [ -f "$DEPLOY_DB" ]; then
  cp "$DEPLOY_DB" "$BACKEND_DB"
  echo "Created $BACKEND_DB from deploy bundle"
fi

mkdir -p /data 2>/dev/null || true

pick_seed() {
  if [ -f "$DEPLOY_DB" ]; then echo "$DEPLOY_DB"; return; fi
  if [ -f "$BACKEND_DB" ]; then echo "$BACKEND_DB"; return; fi
}

seed=$(pick_seed)

if [ -d /data ] && [ -w /data ]; then
  if [ -n "$seed" ]; then
    if [ ! -f "$TARGET" ]; then
      cp "$seed" "$TARGET"
      echo "Seeded $TARGET from $seed"
    else
      size=$(wc -c < "$TARGET" 2>/dev/null || echo 0)
      if [ "$size" -lt "$MIN_SEED_BYTES" ]; then
        cp "$seed" "$TARGET"
        echo "Re-seeded $TARGET (was only ${size} bytes)"
      else
        echo "Using existing SQLite at $TARGET (${size} bytes)"
      fi
    fi
  fi
  export DATABASE_URL="sqlite+aiosqlite:////data/test_generator.db"
  echo "Using SQLite at /data/test_generator.db"
elif [ -f "$BACKEND_DB" ]; then
  export DATABASE_URL="sqlite+aiosqlite:////app/backend/test_generator.db"
  echo "Using SQLite at /app/backend/test_generator.db (no writable /data)"
else
  echo "WARNING: No seed database in image — subjects API will be empty until seed_pdfs runs"
  export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:////data/test_generator.db}"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
