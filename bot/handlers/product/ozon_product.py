import asyncio
import logging

from aiogram import types
from aiogram.fsm.context import FSMContext

from ..commands import dp
from ...states import MarketplaceForm
from ...marketplace.ozon import get_full_product_info

logger = logging.getLogger(__name__)

@dp.callback_query(lambda c: c.data == 'parse_ozon_product')
async def handle_parse_ozon_product(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("📥 Отправьте ссылку на товар Ozon:")
    await state.set_state(MarketplaceForm.waiting_for_ozon_product_url)
    await callback_query.answer()

@dp.message(MarketplaceForm.waiting_for_ozon_product_url)
async def process_ozon_product_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    await message.reply("⏳ Получаю информацию...")
    try:
        info = await asyncio.to_thread(get_full_product_info, url, "ozon")
        await message.reply(f"```json\n{info}\n```", parse_mode="Markdown")
    except Exception as e:
        logger.error(e)
        await message.reply("❌ Ошибка при получении информации.")
    finally:
        await state.clear()
