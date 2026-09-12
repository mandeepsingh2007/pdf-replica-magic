#!/bin/bash
# 2 GiB swap — helps Docker build + LLM generation on t3.micro (1 GiB RAM)
set -e
if swapon --show | grep -q '/swapfile'; then
  echo "Swap already enabled"
  exit 0
fi
sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo "Swap enabled:"
free -h
