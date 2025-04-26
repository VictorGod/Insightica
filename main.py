import os
import asyncio
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.bot import DefaultBotProperties  # <— импортируем
from bot.handlers.commands import dp  # ваш Dispatcher

# Загрузка .env
load_dotenv()

# Получаем токен
BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TG_BOT_TOKEN is not set")

# Инициализируем бота с DefaultBotProperties
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/healthz"):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self, format, *args):
            return

    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health server listening on 0.0.0.0:{port}")
    server.serve_forever()

if __name__ == "__main__":
    # Старт health-сервера в фоне
    Thread(target=run_health_server, daemon=True).start()

    # Запуск polling
    logger.info("Starting Telegram polling")
    asyncio.run(dp.start_polling(bot))
