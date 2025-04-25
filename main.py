import os
import asyncio
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from aiogram import Bot
from bot.handlers.commands import dp  # Ваш диспетчер aiogram

# Загрузка переменных из .env
load_dotenv()
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
RENDER_PORT = int(os.getenv("PORT", 8000))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HTTP‐health‐check для Render
def run_health_server():
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
    HTTPServer(("0.0.0.0", RENDER_PORT), HealthHandler).serve_forever()

if __name__ == "__main__":
    # Старт health‐check в отдельном потоке
    Thread(target=run_health_server, daemon=True).start()
    logger.info(f"Health‐check слушает порт {RENDER_PORT}")

    # Старт long polling бота
    logger.info("Старт Telegram long polling…")
    bot = Bot(token=TG_BOT_TOKEN)
    asyncio.run(dp.start_polling(bot))
