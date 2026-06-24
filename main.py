"""
Unified Entry Point for Replit Deployment.

Runs the FastAPI web server and Discord bot in a single container via
multiprocessing. Used for local Replit development only.
For production, Railway runs bot_main.py and web_main.py as separate services.
"""
import asyncio
import logging
import multiprocessing
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReplitRunner")


def run_web_server() -> None:
    """Target function to run the FastAPI web server."""
    import uvicorn
    from app.config import settings

    logger.info("Starting Web Server on port %s...", settings.effective_port)
    uvicorn.run(
        "web_main:app",
        host=settings.web_host,
        port=settings.effective_port,
        reload=False,
        log_level="info",
    )


async def run_discord_bot() -> None:
    """Async function to run the Discord bot."""
    from app.config import settings
    # Import bot_main lazily to avoid module-level side effects (IPv4 policy, health thread)
    from bot_main import TournamentBot

    if not settings.discord_token:
        logger.critical("DISCORD_TOKEN is not set. Exiting.")
        sys.exit(1)

    logger.info("Starting Discord Bot...")
    bot = TournamentBot()
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    logger.info("Initializing Tournament OS (Replit Mode)...")

    # 1. Launch Web Server in a separate process
    web_process = multiprocessing.Process(target=run_web_server, daemon=True)
    web_process.start()

    try:
        # 2. Run Discord Bot in the main event loop
        asyncio.run(run_discord_bot())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        web_process.terminate()
        web_process.join()
