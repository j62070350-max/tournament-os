"""
run_all.py — Runs BOTH Discord bots in ONE Python process, ONE asyncio event loop.

Benefits vs two separate processes:
- Discord.py, aiohttp, and all shared libs are imported once → ~40% less RAM
- Single health-check server owns PORT, no port conflicts
- Each bot has its own async retry loop — a crash in one never kills the other
"""
import asyncio
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Health-check server (starts immediately) ──────────────────────────────────
class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        b = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def log_message(self, *a): pass

_port = int(os.environ.get("PORT", 8080))
threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", _port), _H).serve_forever(),
    daemon=True, name="health",
).start()
print(f"[health] 0.0.0.0:{_port}", flush=True)

# Tell both bot modules to skip their own health servers
os.environ["SKIP_HEALTH_SERVER"] = "1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("run_all")

# ── Import both bot modules ───────────────────────────────────────────────────
# Since __name__ != "__main__", their asyncio.run(main()) guard doesn't fire.
# All shared libraries (discord.py, aiohttp, groq…) are loaded only once.
logger.info("Importing bot_main…")
import bot_main          # noqa: E402

logger.info("Importing mech_bot_main…")
import mech_bot_main     # noqa: E402

logger.info("Both modules imported. Starting bots…")


# ── Async retry wrapper ───────────────────────────────────────────────────────
async def _run_with_retry(name: str, coro_fn, startup_delay: int = 0) -> None:
    """
    Run coro_fn() forever, restarting on any exit/crash.
    startup_delay lets the mech bot wait for the tournament bot to finish migrations.
    SystemExit (from sys.exit() inside main()) is caught and retried — it does NOT
    kill the whole process.
    """
    if startup_delay:
        logger.info("[%s] Waiting %ds before first start…", name, startup_delay)
        await asyncio.sleep(startup_delay)

    retry_delay = 10
    attempt = 0
    while True:
        attempt += 1
        logger.info("[%s] Starting (attempt %d)…", name, attempt)
        try:
            await coro_fn()
            logger.warning("[%s] main() returned — restarting in %ds", name, retry_delay)
        except SystemExit as exc:
            logger.error(
                "[%s] sys.exit(%s) called — check required env vars. Retrying in %ds",
                name, exc.code, retry_delay,
            )
        except Exception as exc:
            logger.error("[%s] Crashed: %s — retrying in %ds", name, exc, retry_delay, exc_info=True)
        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 120)


async def main() -> None:
    await asyncio.gather(
        _run_with_retry("tournament-bot", bot_main.main, startup_delay=0),
        _run_with_retry("mech-bot",       mech_bot_main.main, startup_delay=20),
        return_exceptions=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
