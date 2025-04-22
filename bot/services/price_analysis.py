import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
from aiogram import types

from ..config import REPORTS_DIR

async def create_price_analysis(message: types.Message, df: pd.DataFrame, category: str):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fn = f"price_analysis_{category}_{ts}.png"
    path = os.path.join(REPORTS_DIR, fn)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))
    ax1.hist(df["price_clean"], bins=30, alpha=0.7)
    ax1.set(title="Распределение цен", xlabel="Цена", ylabel="Кол‑во")
    ax1.grid(alpha=0.3)

    stats = (
        f"Min: {df['price_clean'].min():.2f}\n"
        f"Max: {df['price_clean'].max():.2f}\n"
        f"Mean: {df['price_clean'].mean():.2f}\n"
        f"Median: {df['price_clean'].median():.2f}"
    )
    ax1.text(0.95, 0.95, stats,
             transform=ax1.transAxes, va="top", ha="right",
             bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

    ax2.scatter(df["rating"], df["price_clean"], alpha=0.5)
    ax2.set(title="Цена vs Рейтинг", xlabel="Рейтинг", ylabel="Цена")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()

    await message.reply_document(path, caption="📈 Анализ цен в категории")
