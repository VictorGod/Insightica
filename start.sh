#!/usr/bin/env bash
set -e

# 1) Health-check для Render (порт $PORT)
echo "==> Starting health-check on port ${PORT:-8000}…"
python3 - << 'PYCODE'
import os, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

port = int(os.getenv("PORT", 8000))
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

srv = HTTPServer(("0.0.0.0", port), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
print(f"Health-check running on port {port}")
PYCODE

# 2) Запускаем Telegram-бота
echo "==> Launching Telegram bot…"
exec python3 main.py
