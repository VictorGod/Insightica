import asyncio
import logging
import os
from datetime import datetime

import pandas as pd
from aiogram import types
from aiogram.fsm.context import FSMContext

from ..commands import dp, marketplace_keyboard
from ...config import CSV_DIR
from ...states import MarketplaceForm
from ...services.selenium_utils import get_webdriver
from ...services.parsers import normalize_characteristics
from ...services.price_analysis import create_price_analysis
from ...marketplace.wildberries import parse_wb_category_by_pagination

logger = logging.getLogger(__name__)

@dp.callback_query(lambda c: c.data == 'parse_wb_category')
async def handle_parse_wb_category(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer(
        "📥 Отправьте ссылку на категорию Wildberries\n"
        "Пример: https://www.wildberries.ru/catalog/elektronika/smartfony-i-telefony"
    )
    await state.set_state(MarketplaceForm.waiting_for_wb_category_url)
    await callback_query.answer()

@dp.message(MarketplaceForm.waiting_for_wb_category_url)
async def process_wb_category_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if "wildberries.ru/catalog" not in url:
        return await message.reply("❌ Некорректная ссылка на категорию Wildberries.")
    await state.update_data(category_url=url)
    await message.reply("Сколько товаров собрать? Введите число:")
    await state.set_state(MarketplaceForm.waiting_for_wb_item_count)

@dp.message(MarketplaceForm.waiting_for_wb_item_count)
async def process_wb_item_count(message: types.Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        return await message.reply("❌ Введите положительное целое число.")

    data = await state.get_data()
    url = data["category_url"]
    await message.reply("⏳ Запускаю парсинг...")
    products = await asyncio.to_thread(parse_wb_category_by_pagination, url, count)

    if not products:
        await message.reply("❌ Не удалось собрать товары.")
        return await state.clear()

    # Сохраняем результат в Excel
    name = url.rstrip("/").split("/")[-1]
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    fn   = f"wb_{name}_{ts}.xlsx"
    path = os.path.join(CSV_DIR, fn)
    df   = pd.DataFrame(products)

    # Разворачиваем колонку parameters, если есть
    if "parameters" in df.columns:
        params = df["parameters"].apply(lambda x: pd.Series(x) if isinstance(x, dict) else pd.Series())
        tuples = [tuple(c.split(".",1)) if "." in c else ("",c) for c in params.columns]
        params.columns = pd.MultiIndex.from_tuples(tuples)
        df = pd.concat([df.drop(columns=["parameters"]), params], axis=1)

    df.to_excel(path, index=False)
    await message.reply_document(types.FSInputFile(path), caption=f"📊 Собрано {len(products)} товаров")
    await state.clear()