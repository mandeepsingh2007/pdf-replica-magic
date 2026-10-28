#!/bin/bash
# Run ON EC2 after: ssh -i test-gen-key.pem ubuntu@13.203.207.77
# Same path as original semester deploy (docker image test-gen + /data volume).
set -euo pipefail

cd ~/pdf-replica-magic
git fetch origin main
git reset --hard origin/main

# Force reseed so Hindi-1/2/3 from test_generator.db.deploy replace English-only /data DB
sudo rm -f /data/test_generator.db

sudo docker build -t test-gen .

# Keep existing env if present; otherwise recreate without CORS_ORIGINS (same as last working run)
if [ ! -f /tmp/test-gen.env ]; then
  cat > /tmp/test-gen.env <<'EOF'
DATABASE_URL=sqlite+aiosqlite:////data/test_generator.db
SKIP_IMAGE_EXPAND=1
SKIP_RUNTIME_VLM=1
LLM_MAX_CONCURRENT=1
MAX_LLM_CONTEXT_CHARS=8000
EOF
  echo "NOTE: Add GEMINI_API_KEY to /tmp/test-gen.env if missing, then re-run container."
fi

sudo docker rm -f test-gen 2>/dev/null || true
sudo docker run -d --name test-gen --restart unless-stopped \
  -p 8000:8000 -v /data:/data --env-file /tmp/test-gen.env test-gen

sleep 15
curl -s http://127.0.0.1:8000/health; echo
curl -s "http://127.0.0.1:8000/api/subjects?track=hindi" | head -c 400; echo
