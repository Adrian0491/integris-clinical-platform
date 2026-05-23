#!/bin/sh
# =============================================================================
# Worker startup script
# Launches the Celery worker and a minimal health-check HTTP server in parallel.
# Cloud Run requires a process to listen on $PORT (default 8080).
# =============================================================================

set -e

PORT="${PORT:-8080}"

# ── Health check companion (tiny Python HTTP server) ─────────────────────────
python - << 'PYEOF' &
import http.server, os, threading

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","component":"worker"}')
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *args):
        pass  # suppress access logs

port = int(os.environ.get("PORT", 8080))
server = http.server.HTTPServer(("0.0.0.0", port), HealthHandler)
server.serve_forever()
PYEOF

HEALTH_PID=$!

# ── Celery worker ─────────────────────────────────────────────────────────────
echo "[worker] Starting Celery worker..."
exec celery -A app.workers.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    -Q validation \
    --without-heartbeat \
    --without-gossip \
    --without-mingle
