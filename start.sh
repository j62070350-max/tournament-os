#!/bin/bash

# ─────────────────────────────────────────────────────────────────────────────
# Runs BOTH Discord bots independently in one Railway service.
# Each bot has its own retry loop — a crash in one does NOT kill the other.
# The service only exits (triggering Railway restart) if BOTH bots give up.
# ─────────────────────────────────────────────────────────────────────────────

# Health-check server on PORT — starts immediately so Railway never times out
python3 -c "
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b\"{\\\"status\\\":\\\"ok\\\"}\"
        self.send_response(200)
        self.send_header(\"Content-Type\", \"application/json\")
        self.send_header(\"Content-Length\", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
port = int(os.environ.get(\"PORT\", 8080))
print(f\"[health] 0.0.0.0:{port}\", flush=True)
HTTPServer((\"0.0.0.0\", port), H).serve_forever()
" &
echo "[startup] health server started"
sleep 1

# Tournament bot — retries forever on crash (DB may be temporarily unavailable)
run_tournament_bot() {
  local delay=10
  local attempt=0
  while true; do
    attempt=$((attempt + 1))
    echo "[bot] Starting Tournament Bot (attempt $attempt)..."
    SKIP_HEALTH_SERVER=1 python3 bot_main.py
    echo "[bot] Tournament Bot exited (attempt $attempt). Retrying in ${delay}s..."
    sleep $delay
    [ $delay -lt 120 ] && delay=$((delay * 2))
  done
}

# Mech Arena bot — retries forever on crash
run_mech_bot() {
  local delay=10
  local attempt=0
  # Stagger start so tournament bot DB migrations finish first
  echo "[mech] Waiting 30s before starting Mech Arena Bot..."
  sleep 30
  while true; do
    attempt=$((attempt + 1))
    echo "[mech] Starting Mech Arena Bot (attempt $attempt)..."
    SKIP_HEALTH_SERVER=1 python3 mech_bot_main.py
    echo "[mech] Mech Arena Bot exited (attempt $attempt). Retrying in ${delay}s..."
    sleep $delay
    [ $delay -lt 120 ] && delay=$((delay * 2))
  done
}

# Run both bots in background subshells
run_tournament_bot &
BOT_PID=$!

run_mech_bot &
MECH_PID=$!

echo "[startup] Tournament Bot loop PID=$BOT_PID  Mech Bot loop PID=$MECH_PID"

# Wait for both loops to exit (they loop forever, so this only happens on SIGTERM)
wait $BOT_PID $MECH_PID
