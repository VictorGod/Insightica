import logging
import os

from aiogram import Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

# Единственный Dispatcher
dp = Dispatcher(storage=MemoryStorage())

# Токен из config (используйте, если понадобится внутри хэндлеров)
from bot.config import TG_BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def marketplace_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Парсинг категории Wildberries", callback_data="parse_wb_category")],
        [types.InlineKeyboardButton(text="Парсинг категории Ozon",        callback_data="parse_ozon_category")],
        #[types.InlineKeyboardButton(text="Информация о товаре WB",      callback_data="parse_wb_product")],
        #[types.InlineKeyboardButton(text="Информация о товаре Ozon",    callback_data="parse_ozon_product")],
        [types.InlineKeyboardButton(text="Анализ цен из CSV",          callback_data="analyze_prices")],
        #[types.InlineKeyboardButton(text="Мониторинг цен",             callback_data="price_monitoring")],
        #[types.InlineKeyboardButton(text="Помощь",                      callback_data="help")],
    ])

@dp.message(Command("start"))
async def handle_start(message: types.Message):
    text = (
        "👋 Привет! Я бот для парсинга маркетплейсов. Вот что я умею:\n\n"
        "📊 Парсинг категорий товаров с Wildberries и Ozon\n"
        "🔍 Получение детальной информации о товарах\n"
        "📈 Анализ цен и создание отчётов\n"
        "⏱ Мониторинг изменения цен\n\n"
        "Выберите действие из меню ниже:"
    )
    await message.answer(text, reply_markup=marketplace_keyboard())

@dp.message(Command("help"))
async def handle_help(message: types.Message):
    text = (
        "📚 **Справка по использованию бота**\n\n"
        "Бот позволяет парсить данные с маркетплейсов Wildberries и Ozon.\n\n"
        "**Основные команды:**\n"
        "/start – Главное меню\n"
        "/help  – Эта справка\n\n"
        "**Функции меню:**\n"
        "• Парсинг категории Wildberries\n"
        "• Парсинг категории Ozon\n"
        "• Информация о товаре WB\n"
        "• Информация о товаре Ozon\n"
        "• Анализ цен из CSV\n"
        "• Мониторинг цен\n"
    )
    await message.answer(text)
