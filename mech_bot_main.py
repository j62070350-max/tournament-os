"""
Mech Arena AI Assistant Bot — entrypoint.
Completely independent from the Tournament Bot.
Uses a separate Discord token (MECH_DISCORD_TOKEN).
No database dependency — knowledge is file-based.
"""
import asyncio
import logging
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


# ── Health-check HTTP server (stdlib, daemon thread) ─────────────────────────
# Starts BEFORE asyncio.run() so Railway sees a healthy port immediately,
# even while migrations and Discord login are still in progress.
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass  # suppress access log noise

def _start_health_server() -> None:
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    print(f"Health-check server listening on 0.0.0.0:{port}", flush=True)
    server.serve_forever()

# Start BEFORE asyncio so Railway health check passes immediately on deploy
if not os.environ.get("SKIP_HEALTH_SERVER"):
    threading.Thread(target=_start_health_server, daemon=True, name="health-server").start()
# ─────────────────────────────────────────────────────────────────────────────

# ── Force IPv4 (same fix as bot_main.py) ─────────────────────────────────────
class _IPv4SelectorEventLoop(asyncio.SelectorEventLoop):
    async def getaddrinfo(self, host, port, *, family=0, type=0, proto=0, flags=0):
        return await super().getaddrinfo(
            host, port, family=socket.AF_INET, type=type, proto=proto, flags=flags
        )

class _IPv4EventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self) -> _IPv4SelectorEventLoop:
        return _IPv4SelectorEventLoop()

asyncio.set_event_loop_policy(_IPv4EventLoopPolicy())
# ─────────────────────────────────────────────────────────────────────────────

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from app.mech_arena.config import mech_settings

logging.basicConfig(
    level=getattr(logging, mech_settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class MechArenaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        # members intent disabled: syncing member lists costs ~100MB RAM per bot startup
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        super().__init__(
            command_prefix="!mech ",
            intents=intents,
            description="Mech Arena AI Assistant",
            connector=connector,
            max_messages=100,  # limit message cache (default 1000)
        )

    async def setup_hook(self) -> None:
        logger.info("Loading Mech Arena cogs...")
        await self.load_extension("app.mech_arena.bot.cogs.mech_ai_cog")
        logger.info("Loaded mech_ai_cog")

        try:
            synced = await self.tree.sync()
            logger.info("Synced %d slash commands globally", len(synced))
        except Exception as e:
            logger.error("Failed to sync commands: %s", e)

        @self.tree.error
        async def on_tree_error(
            interaction: discord.Interaction, error: app_commands.AppCommandError
        ) -> None:
            logger.error(
                "App command error in '%s': %s",
                interaction.command.name if interaction.command else "?",
                error,
                exc_info=True,
            )
            msg = "❌ An unexpected error occurred. Please try again."
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass

    async def on_ready(self) -> None:
        logger.info("Mech Arena Bot ready: %s (ID: %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="Mech Arena | /create-mech-ai-channel",
            )
        )
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                n = await self.tree.sync(guild=guild)
                logger.info("Guild-synced %d commands to '%s'", len(n), guild.name)
            except Exception as e:
                logger.warning("Could not guild-sync to '%s': %s", guild.name, e)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info("Joined guild: %s (ID: %s)", guild.name, guild.id)
        try:
            self.tree.copy_global_to(guild=guild)
            n = await self.tree.sync(guild=guild)
            logger.info("Guild-synced %d commands to new guild '%s'", len(n), guild.name)
        except Exception as e:
            logger.warning("Could not guild-sync to '%s': %s", guild.name, e)


async def main() -> None:
    if not mech_settings.mech_discord_token:
        logger.critical("MECH_DISCORD_TOKEN is not set. Exiting.")
        sys.exit(1)

    delay = 10
    max_delay = 300
    attempt = 0

    while True:
        attempt += 1
        try:
            bot = MechArenaBot()
            async with bot:
                await bot.start(mech_settings.mech_discord_token)
            break
        except discord.errors.HTTPException as exc:
            if exc.status == 429:
                retry_after = getattr(exc, "retry_after", None) or delay
                logger.warning("Rate-limited (attempt %d). Retry in %.1fs...", attempt, retry_after)
                await asyncio.sleep(retry_after)
                delay = min(delay * 2, max_delay)
            else:
                logger.error("Discord HTTP error: %s", exc, exc_info=True)
                raise
        except (OSError, ConnectionError) as exc:
            logger.warning("Network error (attempt %d): %s. Retry in %ds...", attempt, exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)


if __name__ == "__main__":
    asyncio.run(main())


