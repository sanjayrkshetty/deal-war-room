# Deployment — free-tier public showcase

Frontend on Vercel · API on Render free. No auth by design; guardrails cap
abuse (daily Groq token budget, per-IP rate limits, fixture reseed on boot).

## One-time setup

### 1. Render (API)

1. Push `main` to GitHub (done continuously).
2. dashboard.render.com → New → Blueprint → pick `sanjayrkshetty/deal-war-room`
   — it reads `render.yaml`.
3. When prompted, fill the secret: `GROQ_API_KEY` (same value as your local
   `backend/.env`).
4. Deploy. Note the service URL, e.g. `https://dwr-api.onrender.com`.
5. Verify `GET /health` → `"db_ok": true`, `"demo.embedder_enabled": false`.

Notes:
- Free tier sleeps after ~15 min idle → first visit cold-starts (~60s).
- SQLite is ephemeral: fixtures reseed on every boot (`DWR_SEED_FIXTURES=true`).
- `/search` returns 503 by design (embedder disabled to keep the image light).

### 2. Vercel (frontend)

1. vercel.com → Add New Project → import `sanjayrkshetty/deal-war-room`.
2. Root directory: `frontend`. Framework: Next.js (auto).
3. Environment variable:
   - `NEXT_PUBLIC_API_BASE` = your Render URL from step 1.4.
4. Deploy → note the domain, e.g. `https://deal-war-room.vercel.app`.

### 3. Close the loop

- Render → `DWR_CORS_ORIGINS`: add your real Vercel domain, redeploy.
- Visit `/health` from the browser, then run one analysis end-to-end.

## Pre-launch audit (rerun before going public)

```bash
# no confidential strings in tracked files
rg -i "sisainfosec\.com|ashish|kalyan|nagaraja" -g '!.env*' --stats || echo CLEAN

# secrets never tracked
git check-ignore backend/.env && echo IGNORED

# caps present in blueprint
rg "DWR_DAILY_TOKEN_BUDGET|DWR_MAX_ANALYSES_PER_HOUR" render.yaml
```

## Model rotation drill

When Groq retires a pinned model ID: hit `GET /models` on their API with your
key, pick replacements, update `DWR_MODEL_TRIAGE` / `DWR_MODEL_SYNTH` in
Render env + local `.env`. No code changes.
