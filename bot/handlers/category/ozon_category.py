import asyncio
import logging
import os
from datetime import datetime

import pandas as pd
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from ..commands import dp
from ...config import CSV_DIR
from ...states import MarketplaceForm
from ...services.selenium_utils import get_webdriver
from ...services.parsers import normalize_characteristics
from ...services.price_analysis import create_price_analysis
from ...marketplace.ozon import parse_ozon_category

logger = logging.getLogger(__name__)

@dp.callback_query(lambda c: c.data == 'parse_ozon_category')
async def handle_parse_ozon_category(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer(
        "📥 Отправьте ссылку на категорию Ozon\n"
        "Пример: https://www.ozon.ru/category/smartfony-15502/"
    )
    await state.set_state(MarketplaceForm.waiting_for_ozon_category_url)
    await callback_query.answer()

@dp.message(MarketplaceForm.waiting_for_ozon_category_url)
async def process_ozon_category_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if "ozon.ru/category" not in url and "ozon.ru/brand" not in url:
        return await message.reply("❌ Некорректная ссылка на категорию Ozon.")
    await state.update_data(category_url=url)
    await message.reply("Сколько товаров собрать? Введите число:")
    await state.set_state(MarketplaceForm.waiting_for_ozon_item_count)

@dp.message(MarketplaceForm.waiting_for_ozon_item_count)
async def process_ozon_item_count(message: types.Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        return await message.reply("❌ Введите положительное целое число.")

    data = await state.get_data()
    url = data["category_url"]
    await message.reply("⏳ Запускаю парсинг...")
    products = await asyncio.to_thread(parse_ozon_category, url, count)

    if not products:
        await message.reply("❌ Не удалось собрать товары.")
        return await state.clear()

    name = url.rstrip("/").split("/")[-1]
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    fn   = f"ozon_{name}_{ts}.xlsx"
    path = os.path.join(CSV_DIR, fn)
    df   = pd.DataFrame(products)
    df.to_excel(path, index=False)

    await message.reply_document(types.FSInputFile(path), caption=f"📊 Собрано {len(products)} товаров")
    await create_price_analysis(message, df, name)
    await state.clear()