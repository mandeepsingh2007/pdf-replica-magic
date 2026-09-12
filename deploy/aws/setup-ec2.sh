#!/bin/bash
# One-time setup on Ubuntu 22.04/24.04 EC2 (t3.micro free tier).
# Usage: curl -fsSL ... | bash   OR   bash deploy/aws/setup-ec2.sh
set -euo pipefail

APP_DIR=/opt/test-generator
REPO="${REPO:-https://github.com/mandeepsingh2007/pdf-replica-magic.git}"
BRANCH="${BRANCH:-main}"

echo "==> Packages"
sudo apt-get update -qq
sudo apt-get install -y -qq git curl ca-certificates nginx

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi

echo "==> Swap (recommended on 1 GiB instances)"
bash "$(dirname "$0")/enable-swap.sh" || true

echo "==> Directories"
sudo mkdir -p "$APP_DIR/data"
sudo chown -R "$USER:$USER" "$APP_DIR"

if [ ! -d "$APP_DIR/repo/.git" ]; then
  echo "==> Clone repo"
  git clone --depth 1 -b "$BRANCH" "$REPO" "$APP_DIR/repo"
else
  echo "==> Pull latest"
  git -C "$APP_DIR/repo" pull --ff-only origin "$BRANCH" || true
fi

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/repo/deploy/aws/env.example" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo ""
  echo "IMPORTANT: Edit $APP_DIR/.env and set GEMINI_API_KEY, then re-run:"
  echo "  cd $APP_DIR/repo && docker compose -f deploy/aws/docker-compose.yml up -d --build"
  exit 0
fi

echo "==> Build & start API"
cd "$APP_DIR/repo"
docker compose -f deploy/aws/docker-compose.yml up -d --build

echo ""
echo "API listening on http://127.0.0.1:8000 (configure nginx + HTTPS next)."
echo "Health: curl -s http://127.0.0.1:8000/health"
