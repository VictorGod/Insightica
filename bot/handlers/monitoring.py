import logging
from aiogram import types

from bot.handlers.commands import dp

logger = logging.getLogger(__name__)

@dp.callback_query(lambda c: c.data == 'price_monitoring')
async def handle_price_monitoring(callback_query: types.CallbackQuery):
    """
    Обработчик кнопки 'Мониторинг цен'.
    Пока просто отвечает заглушкой.
    """
    await callback_query.message.answer("🔄 Настройка мониторинга пока не реализована.")
    await callback_query.answer()
