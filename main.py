import os
import asyncio
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.bot import DefaultBotProperties
from bot.handlers.commands import dp

import aiohttp

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

async def ping_loop():
    url = "https://bba9mgrrav1hm9jcg23l.containers.yandexcloud.net/"
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            try:
                async with session.get(url) as resp:
                    logger.info(f"Ping {url} — статус {resp.status}")
            except Exception as e:
                logger.warning(f"Ошибка при ping: {e}")
            await asyncio.sleep(30)

async def resilient_ping():
    while True:
        try:
            await ping_loop()
        except Exception as e:
            logger.error(f"Ping задание упало: {e}. Перезапуск через 5 секунд.")
            await asyncio.sleep(5)

if __name__ == "__main__":
    # Старт health-сервера в фоне
    Thread(target=run_health_server, daemon=True).start()

    # Запуск polling и resilient_ping параллельно
    async def main():
        await asyncio.gather(
            dp.start_polling(bot),
            resilient_ping()
        )

    logger.info("Запуск Telegram polling и resilient ping")
    asyncio.run(main())
