import os
import logging
from aiohttp import web
from aiogram import Bot
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Импортируем диспетчер с уже зарегистрированными хендлерами
from bot.handlers.commands import dp

load_dotenv()

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "bba9mgrrav1hm9jcg23l.containers.yandexcloud.net")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Получаем порт из переменной окружения, установленной Yandex Cloud
try:
    PORT = int(os.environ.get("PORT", 8080))
except ValueError:
    logger.warning("Invalid PORT value, using default 8080")
    PORT = 8080

logger.info(f"Using port: {PORT}")

if not BOT_TOKEN:
    raise RuntimeError("TG_BOT_TOKEN must be set")

# Инициализируем Bot
bot = Bot(token=BOT_TOKEN)

# Контроллер aiohttp для webhook
handler = SimpleRequestHandler(dispatcher=dp, bot=bot)

# Добавляем простой обработчик корневого пути для проверки работоспособности
async def health_check(request):
    return web.Response(text="Bot is running")

# Хуки запуска/выключения
async def on_startup(app):
    # Регистрируем webhook в Telegram
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown(app):
    # Удаляем webhook и закрываем сессию
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Webhook deleted, session closed")

# Собираем aiohttp-приложение
app = web.Application()
app.add_routes([web.get('/', health_check)])  # Добавляем простой обработчик для проверки
handler.register(app, path=WEBHOOK_PATH)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    logger.info(f"Starting bot with webhook at {WEBHOOK_URL}")
    # Запускаем встроенный aiohttp-сервер
    web.run_app(app, host="0.0.0.0", port=PORT)
