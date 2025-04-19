import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from aiogram.fsm.storage.memory import MemoryStorage

# Load environment variables
load_dotenv()

# Initialize the bot and dispatcher
bot = Bot(token=os.getenv("TG_BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

# Configure logging
logging.basicConfig(level=logging.INFO)

# Import handlers after initializing Dispatcher
from bot.handlers import dp  

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
