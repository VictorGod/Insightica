import asyncio
import logging
import os

from dotenv import load_dotenv
from aiogram import Bot

# Загрузка .env
load_dotenv()

# Инициализация бота
bot = Bot(token=os.getenv("TG_BOT_TOKEN"))

# Логирование
logging.basicConfig(level=logging.INFO)

# Импортируем диспетчер из handlers
from bot.handlers.commands import dp

if __name__ == "__main__":
    # Запускаем polling
    asyncio.run(dp.start_polling(bot))
