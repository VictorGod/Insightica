import os
import logging
import shutil
from aiohttp import web
from aiogram import Bot
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Импорт диспетчера с хендлерами
from bot.handlers.commands import dp

load_dotenv()

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "bba9mgrrav1hm9jcg23l.containers.yandexcloud.net")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Порт из переменных Yandex.Cloud
try:
    PORT = int(os.environ.get("PORT", 8080))
except ValueError:
    logger.warning("Invalid PORT value, using default 8080")
    PORT = 8080

logger.info(f"Using port: {PORT}")

if not BOT_TOKEN:
    raise RuntimeError("TG_BOT_TOKEN must be set")

# Функция для чтения использования диска
def get_disk_usage(path: str):
    total, used, free = shutil.disk_usage(path)
    return {
        "total_mb": round(total / 1024**2, 1),
        "used_mb":  round(used  / 1024**2, 1),
        "free_mb":  round(free  / 1024**2, 1),
    }

# Логируем сразу при старте
root_usage = get_disk_usage("/")
tmp_usage  = get_disk_usage("/tmp")
logger.info(f"Disk /  : {root_usage}")
logger.info(f"Disk /tmp: {tmp_usage}")

# Инициализируем Bot
bot = Bot(token=BOT_TOKEN)
handler = SimpleRequestHandler(dispatcher=dp, bot=bot)

# Health-check отдаёт JSON с дисковым пространством
async def health_check(request):
    return web.json_response({
        "status": "ok",
        "disk_root": get_disk_usage("/"),
        "disk_tmp":  get_disk_usage("/tmp"),
    })

# Хуки для webhook
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Webhook deleted, session closed")

# Собираем aiohttp-приложение
app = web.Application()
app.add_routes([web.get('/', health_check)])
handler.register(app, path=WEBHOOK_PATH)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    logger.info(f"Starting bot with webhook at {WEBHOOK_URL}")
    web.run_app(app, host="0.0.0.0", port=PORT)
