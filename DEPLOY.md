# Free deploy — Frontend (Vercel) + Backend (Render)

Login stays on **Vercel**. Test generation API runs on **Render** (free tier).  
Vercel proxies `/api/backend/*` to Render — no extra CORS setup for the browser.

## What you need

- [GitHub](https://github.com) account + repo with this project
- [Vercel](https://vercel.com) account (free)
- [Render](https://render.com) account (free)
- **GEMINI_API_KEY** (same as local `.env`)

**Free tier limits:** Render sleeps after ~15 min idle (first request slow). SQLite on Render survives restarts but can reset on **redeploy** — keep a copy of `test_generator.db.deploy`.

---

## Step 1 — Prepare data for the cloud (once, on your PC)

Your Class 1 PDFs + DB must be in the repo (or Docker image).

```powershell
cd "C:\test generator"

# 1) Ensure local DB is seeded (if not already)
cd backend
python seed_pdfs.py
cd ..

# 2) Build Linux-friendly DB copy (paths → /app/test pdf/...)
python backend/scripts/prepare_deploy_db.py
```

Add to git (large files — use Git LFS if GitHub complains):

- `backend/test_generator.db.deploy`
- `test pdf/original books/class 1 sem 1/` (PDFs + `images_*` folders)

```powershell
git add backend/test_generator.db.deploy "test pdf/original books"
git commit -m "Add deploy bundle for Class 1 Sem 1"
git push
```

---

## Step 2 — Deploy backend (Render)

1. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint** (or **Web Service** → Docker).
2. Connect your GitHub repo.
3. Use repo root; **Dockerfile** path: `./Dockerfile`.
4. **Environment variables:**

   | Key | Value |
   |-----|--------|
   | `GEMINI_API_KEY` | your key |
   | `DATABASE_URL` | `sqlite+aiosqlite:////data/test_generator.db` |
   | `CORS_ORIGINS` | `["https://YOUR-APP.vercel.app"]` (update after Vercel) |

5. Deploy. Copy the public URL, e.g. `https://test-generator-api.onrender.com`.
6. Check: `https://YOUR-API.onrender.com/health` → `{"status":"healthy",...}`  
   Check: `https://YOUR-API.onrender.com/api/subjects` → JSON list of subjects.

---

## Step 3 — Deploy frontend (Vercel)

1. [vercel.com/new](https://vercel.com/new) → Import GitHub repo.
2. **Root Directory:** `frontend`
3. **Environment variables:**

   | Key | Value |
   |-----|--------|
   | `BACKEND_URL` | `https://YOUR-API.onrender.com` (no trailing slash) |

   Do **not** set `NEXT_PUBLIC_API_URL` — the app uses `/api/backend` on Vercel.

4. Deploy. Note your URL, e.g. `https://test-generator-xxx.vercel.app`.

5. Back on **Render**, set `CORS_ORIGINS` to include your Vercel URL (optional if you only use Vercel proxy).

---

## Step 4 — Test

1. Open Vercel URL → **Test Generator** → login (`testid` / `NeGraphics@2026`).
2. Subjects should load; generate a small test.

---

## Login credentials (unchanged)

- **ID:** `testid`
- **Password:** `NeGraphics@2026`

Change these in `frontend/src/app/api/login/route.ts` before public production if needed.

---

## Troubleshooting

| Problem | Fix |
|--------|-----|
| Subjects empty / 502 | Wake Render (open `/health`), check `BACKEND_URL` on Vercel |
| “PDF not ingested” | DB/PDF paths wrong — re-run `prepare_deploy_db.py`, redeploy |
| Render build OOM | Use paid plan or slim deps; free tier has memory limits |
| Slow first request | Normal on Render free (cold start) |

---

## Optional: custom domain

- Vercel: Project → **Domains** → add `www.negraphics.in` (you already use this in CORS locally).
- Render: add subdomain `api.negraphics.in` → point CNAME to Render.
- Vercel `BACKEND_URL=https://api.negraphics.in`

---

## Cost summary

| Service | Free tier |
|---------|-----------|
| Vercel | Hobby — Next.js OK |
| Render | Free web service — sleeps when idle |
| Gemini API | Google quota / billing (not free unlimited) |

No credit card required for Vercel + Render hobby in most regions.
