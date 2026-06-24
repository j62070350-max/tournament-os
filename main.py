"""
Unified Entry Point for Replit Deployment.

This file allows the bot and web server to run in a single container.
It uses multiprocessing to launch the FastAPI server and the Discord bot.
"""
import asyncio
import multiprocessing
import sys
import logging

from app.config import settings
from bot_main import TournamentBot
from web_main import app
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReplitRunner")

def run_web_server():
    """Target function to run the FastAPI web server."""
    logger.info("Starting Web Server on port %s...", settings.effective_port)
    uvicorn.run(
        "web_main:app",
        host=settings.web_host,
        port=settings.effective_port,
        reload=False,
        log_level="info",
    )

async def run_discord_bot():
    """Async function to run the Discord bot."""
    logger.info("Starting Discord Bot...")
    bot = TournamentBot()
    async with bot:
        await bot.start(settings.discord_token)

if __name__ == "__main__":
    # Replit Agents usually look for 'main.py' as the entry point.
    # This orchestrates both services.
    
    logger.info("Initializing Tournament OS (Replit Mode)...")
    
    # 1. Launch Web Server in a separate process
    web_process = multiprocessing.Process(target=run_web_server)
    web_process.start()
    
    try:
        # 2. Launch Discord Bot in the main event loop
        asyncio.run(run_discord_bot())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        web_process.terminate()
        web_process.join()
