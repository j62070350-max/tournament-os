#!/bin/bash
set -e

# Write the health check server to a temp file
cat > /tmp/_health.py << 'PYEOF'
import os, sys
from http.server import HTTPServer, BaseHTTPRequestHandler

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

port = int(os.environ.get("PORT", 8080))
print(f"[health] listening on 0.0.0.0:{port}", flush=True)
HTTPServer(("0.0.0.0", port), H).serve_forever()
PYEOF

# Start health server in the background BEFORE the bot
python3 /tmp/_health.py &
HEALTH_PID=$!
echo "[startup] health server PID=$HEALTH_PID port=${PORT:-8080}"

# Give it a moment to bind
sleep 1

# Start the bot — exec replaces the shell so signals pass through
exec python3 bot_main.py
