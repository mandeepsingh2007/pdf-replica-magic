#!/bin/bash
# Run ON EC2 after: ssh -i test-gen-key.pem ubuntu@13.203.207.77
# Same path as semester/Hindi deploy (docker image test-gen + /data volume).
set -euo pipefail

cd ~/pdf-replica-magic
echo "=== pull ==="
git fetch origin main
git reset --hard origin/main
git log -1 --oneline

echo "=== disk before ==="
df -h / | tail -1
sudo docker container prune -f || true

# Keep GROQ + LLM_PROVIDER (do not recreate env from scratch)
sudo grep -E '^(LLM_PROVIDER|GROQ_API_KEY|GEMINI_API_KEY|LOW_MEMORY|SKIP_|DATABASE_URL)=' /tmp/test-gen.env \
  | sed -E 's/^(GROQ_API_KEY|GEMINI_API_KEY)=.*/\1=SET/' || true
if ! sudo grep -q '^LLM_PROVIDER=groq' /tmp/test-gen.env 2>/dev/null; then
  if sudo grep -q '^LLM_PROVIDER=' /tmp/test-gen.env 2>/dev/null; then
    sudo sed -i 's/^LLM_PROVIDER=.*/LLM_PROVIDER=groq/' /tmp/test-gen.env
  else
    echo 'LLM_PROVIDER=groq' | sudo tee -a /tmp/test-gen.env >/dev/null
  fi
fi
if ! sudo grep -q '^GROQ_API_KEY=.' /tmp/test-gen.env 2>/dev/null; then
  echo "ERROR: GROQ_API_KEY missing in /tmp/test-gen.env" >&2
  exit 1
fi

# Reseed so SST-6/7 from test_generator.db.deploy land on /data
# (start-api.sh keeps existing DB otherwise)
sudo rm -f /data/test_generator.db
echo "=== DB cleared for Future Books SST reseed ==="

echo "=== build ==="
sudo docker build -t test-gen .
echo "=== restart ==="
sudo docker rm -f test-gen || true
sudo docker run -d --name test-gen --restart unless-stopped \
  -p 8000:8000 -v /data:/data --env-file /tmp/test-gen.env test-gen
sleep 12
curl -sS http://127.0.0.1:8000/health; echo
curl -sS "http://127.0.0.1:8000/api/subjects?track=future" | head -c 500; echo
echo "=== DONE ==="
