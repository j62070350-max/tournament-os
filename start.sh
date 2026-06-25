#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────────────────────
# Single Railway service running BOTH Discord bots.
# One health-check server owns PORT.
# Mech bot starts 30 s after the tournament bot so their startup memory
# peaks (migrations + Discord login vs knowledge-base load) don't overlap.
# If either bot exits, the whole container exits → Railway auto-restarts.
# ─────────────────────────────────────────────────────────────────────────────

# Start health-check server first so Railway sees a live port immediately
python3 -c "
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{\"status\":\"ok\"}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
port = int(os.environ.get('PORT', 8080))
print(f'[health] listening on 0.0.0.0:{port}', flush=True)
HTTPServer(('0.0.0.0', port), H).serve_forever()
" &
HEALTH_PID=$!
echo "[startup] health server PID=$HEALTH_PID"
sleep 1

# Start tournament bot first (heavier: runs DB migrations + Discord login)
SKIP_HEALTH_SERVER=1 python3 bot_main.py &
BOT_PID=$!
echo "[startup] Tournament Bot PID=$BOT_PID"

# Wait 30 s before starting mech bot so startup memory peaks don't overlap
echo "[startup] Waiting 30 s before starting Mech Arena Bot..."
sleep 30

# Start mech bot (loads BM25 knowledge base into memory)
SKIP_HEALTH_SERVER=1 python3 mech_bot_main.py &
MECH_PID=$!
echo "[startup] Mech Arena Bot PID=$MECH_PID"

# If either bot exits for any reason, kill everything → Railway restarts
wait -n $BOT_PID $MECH_PID
echo "[startup] A bot process exited — shutting down so Railway can restart"
kill $BOT_PID $MECH_PID $HEALTH_PID 2>/dev/null
exit 1
