import os
from aiohttp import web
from dotenv import load_dotenv

from aiogram import Bot
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# Берём ваш Dispatcher с уже зарегистрированными хендлерами
from bot.handlers.commands import dp  

load_dotenv()

BOT_TOKEN    = os.getenv("TG_BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")             # например: https://<trigger>.functions.yc.dev
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL  = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT         = int(os.getenv("PORT", 8443))

if not BOT_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("TG_BOT_TOKEN and WEBHOOK_HOST must be set")

# Инициализируем Bot
bot = Bot(token=BOT_TOKEN)                           # aiogram 3 Bot :contentReference[oaicite:3]{index=3}

# Контроллер aiohttp для webhook
handler = SimpleRequestHandler(dispatcher=dp, bot=bot)  # aiohttp-интеграция :contentReference[oaicite:4]{index=4}

# Хуки запуска/выключения
async def on_startup(app: web.Application):
    # Регистрируем webhook в Telegram
    await bot.set_webhook(WEBHOOK_URL)               # метод aiogram.methods.set_webhook :contentReference[oaicite:5]{index=5}

async def on_shutdown(app: web.Application):
    # Удаляем webhook и закрываем сессию
    await bot.delete_webhook()
    await bot.session.close()

# Собираем aiohttp-приложение
app = web.Application()
handler.register(app, path=WEBHOOK_PATH)            # вешаем POST /webhook → Dispatcher.feed_update :contentReference[oaicite:6]{index=6}
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    # Запускаем встроенный aiohttp-сервер
    web.run_app(app, host="0.0.0.0", port=PORT)      # запустить веб-приложение :contentReference[oaicite:7]{index=7}
