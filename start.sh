#!/usr/bin/env bash
set -e

# 1) Запускаем ss-local (Shadowsocks-libev) как root
echo "==> Запуск ss-local (Shadowsocks-libev)…"
ss-local \
  -s "${SS_SERVER}" \
  -p "${SS_SERVER_PORT}" \
  -k "${SS_PASSWORD}" \
  -m "${SS_METHOD}" \
  -l "${SS_LOCAL_PORT}" &

# Даем прокси секундочку поднимется
sleep 2

# 2) Запускаем HTTP-health-check в фоне
echo "==> Запуск health-check на порту ${PORT}…"
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
print(f"Health-check работает на порту {port}")
PYCODE

# 3) Запускаем бота
echo "==> Запуск Telegram-бота…"
exec python3 main.py
