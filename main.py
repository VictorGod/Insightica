import os
import asyncio
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from aiogram import Bot
from bot.handlers.commands import dp  # ваш диспетчер aiogram

# Загрузка переменных окружения из .env
load_dotenv()

# Инициализация бота
bot = Bot(token=os.getenv("TG_BOT_TOKEN"))

# Настройка логирования
logging.basicConfig(level=logging.INFO)

def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            # любой GET на корень отдаёт 200 OK
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# Запускаем HTTP-сервер в демон-потоке
Thread(target=run_health_server, daemon=True).start()

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
