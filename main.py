import os
import asyncio
import logging
import subprocess
import time
import shutil
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from aiogram import Bot
from bot.handlers.commands import dp  # ваш диспетчер aiogram

# -----------------------
# Загрузка переменных
# -----------------------
load_dotenv()

TG_BOT_TOKEN    = os.getenv("TG_BOT_TOKEN")
RENDER_PORT     = int(os.getenv("PORT", 8000))

# Shadowsocks из .env
SS_SERVER       = os.getenv("SS_SERVER")
SS_SERVER_PORT  = os.getenv("SS_SERVER_PORT")
SS_PASSWORD     = os.getenv("SS_PASSWORD")
SS_METHOD       = os.getenv("SS_METHOD")
SS_LOCAL_PORT   = os.getenv("SS_LOCAL_PORT", "1080")

# -----------------------
# Логирование
# -----------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------
# HTTP health‐check для Render
# -----------------------
def run_health_server():
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
    server = HTTPServer(("0.0.0.0", RENDER_PORT), HealthHandler)
    server.serve_forever()

# -----------------------
# Основной запуск
# -----------------------
if __name__ == "__main__":
    # 1) Запуск ss-local, если он доступен в PATH
    if shutil.which("ss-local"):
        logger.info("Starting ss-local (Shadowsocks) proxy...")
        subprocess.Popen([
            "ss-local",
            "-s", SS_SERVER,
            "-p", SS_SERVER_PORT,
            "-k", SS_PASSWORD,
            "-m", SS_METHOD,
            "-l", SS_LOCAL_PORT
        ])
        # даём пару секунд, чтобы прокси поднялся
        time.sleep(2)
    else:
        logger.warning("ss-local not found; proceeding without proxy")

    # 2) Старт health‐check
    Thread(target=run_health_server, daemon=True).start()
    logger.info(f"Health server listening on port {RENDER_PORT}")

    # 3) Старт бота
    logger.info("Starting Telegram long polling...")
    bot = Bot(token=TG_BOT_TOKEN)
    asyncio.run(dp.start_polling(bot))
