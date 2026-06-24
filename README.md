# tournament-os — Discord Bots

Both Discord bots run in a **single Railway service** via `start.sh`.

## Bots

| Bot | Entry Point | Token Env Var |
|-----|-------------|---------------|
| Tournament Bot | `bot_main.py` | `DISCORD_TOKEN` |
| Mech Arena Bot | `mech_bot_main.py` | `MECH_DISCORD_TOKEN` |

## Deploy on Railway (single service)

1. New Railway project → **Deploy from GitHub** → select this repo
2. **One service only** — no need to add a second
3. Leave the **Healthcheck Path** blank (or set to `/`) — Railway will use PORT automatically
4. Set env vars:

```
DATABASE_URL=postgresql://...
DISCORD_TOKEN=your_tournament_bot_token
DISCORD_CLIENT_ID=your_discord_app_client_id
GROQ_API_KEY=your_groq_key
MECH_DISCORD_TOKEN=your_mech_bot_token
ENVIRONMENT=production
LOG_LEVEL=INFO
```

5. Deploy ✅ — `start.sh` starts the health server + both bots together.

If either bot crashes, the whole service exits so Railway auto-restarts everything.

## Web API
Lives in **[tournament-os-web](https://github.com/j62070350-max/tournament-os-web)** → deployed on Vercel.
