# Deployment Guide

## Architecture

| Service | Platform | Config file |
|---------|----------|-------------|
| Web API + Dashboard | **Vercel** | `vercel.json` |
| Tournament Bot | **Railway** | `railway.bot.toml` |
| Mech Arena Bot | **Railway** | `railway.mech.toml` |

---

## Vercel (Web API)

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → Import your GitHub repo
2. Framework Preset: **Other**
3. Set these environment variables in Vercel dashboard:
   - `DATABASE_URL` — your PostgreSQL connection string (Neon/Supabase/Railway Postgres)
   - `ADMIN_DASHBOARD_TOKEN` — a long random string (generate with `openssl rand -hex 32`)
   - `SECRET_KEY` — another long random string
   - `GROQ_API_KEY` — your Groq API key
   - `ENVIRONMENT` — `production`
4. Deploy — Vercel auto-detects `vercel.json` and deploys the FastAPI app

**Important:** Run DB migrations once after first deploy:
```
vercel env pull .env.local
alembic upgrade head
```
Or use your DB provider's migration UI.

---

## Railway (Bots)

### Tournament Bot
1. New Railway project → Deploy from GitHub repo
2. In service settings → **Custom Start Command**: `python bot_main.py`
3. **Config file**: `railway.bot.toml`  
4. Set environment variables:
   - `DATABASE_URL`
   - `DISCORD_TOKEN`
   - `DISCORD_CLIENT_ID`
   - `GROQ_API_KEY`
   - `ENVIRONMENT=production`
5. **IMPORTANT**: In Railway service settings → **Healthcheck** → **Disable** (bots don't need healthchecks)

### Mech Arena Bot
1. Add another service in same Railway project → Deploy from same GitHub repo
2. **Config file**: `railway.mech.toml`
3. Set environment variables:
   - `MECH_DISCORD_TOKEN`
   - `ENVIRONMENT=production`
4. **IMPORTANT**: In Railway service settings → **Healthcheck** → **Disable**

---

## Why healthchecks were failing on Railway

Railway healthchecks send an HTTP request to your service's `$PORT` and expect a 200 response.
The bots bind to `$PORT` **only after** Discord login completes and migrations finish — which can
take 30–60 seconds. Railway's default timeout is shorter, so it kills the service before it's ready.

**Fix applied**: Removed `healthcheckPath` from `railway.bot.toml` and `railway.mech.toml`.
Bots don't expose HTTP — they don't need healthchecks. Railway will keep them running as long
as the process stays alive.
