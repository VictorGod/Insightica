import os
import asyncio
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from aiogram import Bot
from bot.handlers.commands import dp  

# Загрузка переменных окружения из .env
load_dotenv()

# Инициализация бота
bot = Bot(token=os.getenv("TG_BOT_TOKEN"))

# Настройка логирования
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
