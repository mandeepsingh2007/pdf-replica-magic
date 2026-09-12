# Deploy backend on AWS Free Tier (EC2)

Frontend stays on **Vercel** (`www.negraphics.in`). Only the **FastAPI Docker API** runs on AWS.

**Why AWS free tier helps:** SQLite + uploads live on the **EBS disk** attached to your instance. They survive container restarts (unlike Render free ephemeral disk). You still only get **~1 GiB RAM** on `t3.micro` — the same memory-safe env vars as Render apply.

---

## What you need

| Item | Notes |
|------|--------|
| AWS account | [aws.amazon.com](https://aws.amazon.com) — free tier / credits |
| This repo on GitHub | `mandeepsingh2007/pdf-replica-magic` |
| `GEMINI_API_KEY` | Same as local |
| Domain (recommended) | e.g. `api.negraphics.in` → EC2 public IP (A record) |
| Vercel | `BACKEND_URL` → your HTTPS API URL |

**Region:** `ap-south-1` (Mumbai) is fine for India latency.

---

## Step 1 — Launch EC2 (free tier)

1. AWS Console → **EC2** → **Launch instance**.
2. **Name:** `test-generator-api`
3. **AMI:** Ubuntu Server 22.04 LTS (64-bit x86)
4. **Instance type:** `t3.micro` (Free tier eligible)
5. **Key pair:** Create/download `.pem` (you need it for SSH).
6. **Storage:** 20–30 GiB **gp3** root volume (free tier includes some EBS).
7. **Security group:**

   | Type | Port | Source |
   |------|------|--------|
   | SSH | 22 | **My IP** only |
   | HTTP | 80 | 0.0.0.0/0 |
   | HTTPS | 443 | 0.0.0.0/0 |

   Do **not** open port 8000 publicly — nginx will proxy locally.

8. Launch. Note the **Public IPv4 address**.

---

## Step 2 — SSH and run setup script

From PowerShell (path to your `.pem`):

```powershell
ssh -i "C:\path\to\your-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

On the server:

```bash
cd ~
git clone --depth 1 https://github.com/mandeepsingh2007/pdf-replica-magic.git
cd pdf-replica-magic
chmod +x deploy/aws/*.sh
./deploy/aws/setup-ec2.sh
```

Edit secrets:

```bash
nano /opt/test-generator/.env
# Set GEMINI_API_KEY=...
# Save: Ctrl+O, Enter, Ctrl+X
```

Build and start:

```bash
cd /opt/test-generator/repo
docker compose -f deploy/aws/docker-compose.yml up -d --build
```

First build can take **15–25 minutes** on `t3.micro`. Swap is enabled automatically to reduce OOM during `pip install`.

Check:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/subjects
```

---

## Step 3 — HTTPS with nginx (required for Vercel)

1. Point DNS: **`api.negraphics.in`** → **A record** → EC2 public IP (TTL 300).

2. Install certbot and wire nginx:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo cp /opt/test-generator/repo/deploy/aws/nginx-api.conf /etc/nginx/sites-available/test-generator-api
sudo sed -i 's/api.example.com/api.negraphics.in/g' /etc/nginx/sites-available/test-generator-api
sudo ln -sf /etc/nginx/sites-available/test-generator-api /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.negraphics.in
```

3. Browser check: `https://api.negraphics.in/health`

---

## Step 4 — Point Vercel at AWS

Vercel project → **Settings** → **Environment variables**:

| Key | Value |
|-----|--------|
| `BACKEND_URL` | `https://api.negraphics.in` (no trailing slash) |

Redeploy Vercel. Test: `https://www.negraphics.in/upload` → subjects load → generate test.

---

## Updates (after git push)

```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_IP
cd /opt/test-generator/repo
git pull
docker compose -f deploy/aws/docker-compose.yml up -d --build
```

Data in `/opt/test-generator/data` is kept across rebuilds.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Docker build killed | Run `./deploy/aws/enable-swap.sh`, retry build; or build image on a bigger machine and `docker save` / `docker load` |
| `subjects` empty | `curl http://127.0.0.1:8000/health/db` — re-seed: ensure `test_generator.db.deploy` is in repo; wipe `/opt/test-generator/data/test_generator.db` only if you want a fresh seed |
| Vercel 502 | Check `BACKEND_URL`, security group 443, nginx running, cert valid |
| Generation still dies | 1 GiB limit — keep `SKIP_RUNTIME_VLM=1`; upgrade to **t3.small** (2 GiB) when free credits allow |
| Elastic IP | Free tier: allocate **Elastic IP** and attach so IP doesn’t change on stop/start |

---

## Cost (typical)

| Resource | Free tier |
|----------|-----------|
| EC2 t3.micro | 750 h/month × 12 months (legacy accounts) or credits (new accounts) |
| EBS | ~30 GB-month included in many accounts |
| Data transfer | First GB out cheap; monitor in **Billing** |
| Vercel + Gemini | Unchanged |

Set **Billing alarm** at $1–5 in AWS Budgets so you never get surprised.

---

## Optional: stop Render

Once AWS works, remove or pause the Render service and keep only Vercel + AWS + Gemini.
