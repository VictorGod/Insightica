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
from bot.handlers.commands import dp

# Загрузка .env
load_dotenv()
TG_BOT_TOKEN   = os.getenv("TG_BOT_TOKEN")
RENDER_PORT    = int(os.getenv("PORT", 8000))

# Shadowsocks параметры
SS_SERVER      = os.getenv("SS_SERVER")
SS_SERVER_PORT = os.getenv("SS_SERVER_PORT")
SS_PASSWORD    = os.getenv("SS_PASSWORD")
SS_METHOD      = os.getenv("SS_METHOD")
SS_LOCAL_PORT  = os.getenv("SS_LOCAL_PORT", "1080")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_health_server():
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
    HTTPServer(("0.0.0.0", RENDER_PORT), HealthHandler).serve_forever()

if __name__ == "__main__":
    # Проверяем наличие ss-local
    if not shutil.which("ss-local"):
        logger.error("ss-local не найден! shadowsocks-libev не установлен?")
    else:
        # Проверяем переменные
        missing = [k for k,v in {
            "SS_SERVER": SS_SERVER,
            "SS_SERVER_PORT": SS_SERVER_PORT,
            "SS_PASSWORD": SS_PASSWORD,
            "SS_METHOD": SS_METHOD
        }.items() if not v]
        if missing:
            logger.error("Пропущены переменные %s — ss-local не запустится", missing)
        else:
            logger.info("Запускаем ss-local (Shadowsocks) …")
            subprocess.Popen([
                "ss-local",
                "-s", SS_SERVER,
                "-p", SS_SERVER_PORT,
                "-k", SS_PASSWORD,
                "-m", SS_METHOD,
                "-l", SS_LOCAL_PORT
            ])
            time.sleep(2)  # даём прокси подняться

    # Health-check для Render
    Thread(target=run_health_server, daemon=True).start()
    logger.info("Health-check слушает порт %s", RENDER_PORT)

    # Старт бота
    logger.info("Старт long polling…")
    bot = Bot(token=TG_BOT_TOKEN)
    asyncio.run(dp.start_polling(bot))
