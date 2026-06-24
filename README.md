# tournament-os — Discord Bots

Two Discord bots for running tournaments. Deployed on **Railway**.

## Services

| Service | Entry Point | Railway Config |
|---------|-------------|----------------|
| Tournament Bot | `bot_main.py` | `railway.bot.toml` |
| Mech Arena Bot | `mech_bot_main.py` | `railway.mech.toml` |

## Deploy on Railway

1. New Railway project → **Deploy from GitHub** → select this repo
2. Add **two services** from the same repo:
   - Service 1 → Settings → Config File Path: `railway.bot.toml`
   - Service 2 → Settings → Config File Path: `railway.mech.toml`
3. **Leave healthcheck blank** — the health server starts automatically in the code
4. Set env vars per service:

### Tournament Bot
```
DATABASE_URL=postgresql://...
DISCORD_TOKEN=your_token
DISCORD_CLIENT_ID=your_client_id
GROQ_API_KEY=your_groq_key
ENVIRONMENT=production
```

### Mech Arena Bot
```
MECH_DISCORD_TOKEN=your_mech_token
ENVIRONMENT=production
```

## Web API
Lives in **[tournament-os-web](https://github.com/j62070350-max/tournament-os-web)** → deployed on Vercel.
