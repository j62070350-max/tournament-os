#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────────────────────
# Single Railway service that runs BOTH Discord bots.
# One health-check server handles PORT; both bots skip their own via env var.
# If either bot process exits (crash/restart), the whole container exits so
# Railway restarts it automatically.
# ─────────────────────────────────────────────────────────────────────────────

# Start a single health-check server on PORT
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

# Give health server a moment to bind before Railway checks it
sleep 1

# Start both bots with SKIP_HEALTH_SERVER=1 so they don't fight over PORT
SKIP_HEALTH_SERVER=1 python3 bot_main.py &
BOT_PID=$!
echo "[startup] Tournament Bot PID=$BOT_PID"

SKIP_HEALTH_SERVER=1 python3 mech_bot_main.py &
MECH_PID=$!
echo "[startup] Mech Arena Bot PID=$MECH_PID"

# Wait for any child to exit — if a bot crashes, kill everything so Railway restarts
wait -n $BOT_PID $MECH_PID
echo "[startup] A bot process exited — shutting down so Railway can restart"
kill $BOT_PID $MECH_PID $HEALTH_PID 2>/dev/null
exit 1
