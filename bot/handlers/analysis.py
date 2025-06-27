import pandas as pd
import matplotlib.pyplot as plt

from pathlib import Path
from collections import Counter

from aiogram import types
from aiogram.filters.command import Command
from aiogram.types import ContentType, FSInputFile

from .commands import dp

# -------------------------------------------------------------------
# Пути к папкам с данными
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_DIR     = PROJECT_ROOT / "marketplace_data" / "csv"
REPORTS_DIR = PROJECT_ROOT / "marketplace_data" / "reports"
CSV_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Путь к последнему загруженному файлу
_last_uploaded: Path | None = None


def load_last_dataframe() -> pd.DataFrame | None:
    """Загружает DataFrame из последнего присланного или самого свежего файла."""
    global _last_uploaded
    if _last_uploaded and _last_uploaded.exists():
        try:
            return (
                pd.read_excel(_last_uploaded, sheet_name=0)
                if _last_uploaded.suffix.lower() in (".xlsx", ".xls")
                else pd.read_csv(_last_uploaded)
            )
        except Exception:
            return None

    # fallback: самый свежий файл в папке
    files = list(CSV_DIR.glob("*.xlsx")) + list(CSV_DIR.glob("*.xls")) + list(CSV_DIR.glob("*.csv"))
    if not files:
        return None
    last = max(files, key=lambda f: f.stat().st_mtime)
    try:
        return (
            pd.read_excel(last, sheet_name=0)
            if last.suffix.lower() in (".xlsx", ".xls")
            else pd.read_csv(last)
        )
    except Exception:
        return None


@dp.callback_query(lambda c: c.data == 'analyze_prices')
async def handle_analyze_prices(callback_query: types.CallbackQuery):
    await callback_query.message.answer(
        "🛠 Пришлите CSV/XLS/XLSX и, если хотите, сразу укажите в подписи команду:\n"
        "  /summary   — заполненность полей\n"
        "  /price_hist— распределение цен\n"
        "  /discount  — распределение скидок\n"
        "  /chars     — топ-15 характеристик\n"
        "  /compare   — сравнение по категориям\n"
        "  /margin    — маржинальность\n"
        "  /flow      — динамика отзывов"
    )
    await callback_query.answer()


@dp.message(lambda m: m.content_type == ContentType.DOCUMENT)
async def handle_file_upload(message: types.Message):
    global _last_uploaded
    doc = message.document
    ext = Path(doc.file_name or "").suffix.lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        return await message.reply("❌ Поддерживаются только файлы .csv, .xls и .xlsx")
    dest = CSV_DIR / f"{doc.file_id}{ext}"
    tg_file = await message.bot.get_file(doc.file_id)
    await message.bot.download_file(tg_file.file_path, destination=dest)
    _last_uploaded = dest
    await message.reply(f"✅ Сохранено как `{dest.name}`", parse_mode="Markdown")

    # если сразу в подписи команда — выполняем
    if message.caption:
        cmd = message.caption.strip().split()[0].lower()
        mapping = {
            "/summary": cmd_summary_report,
            "/price_hist": cmd_price_distribution,
            "/discount": cmd_discount_analysis,
            "/chars": cmd_characteristics_freq,
            "/compare": cmd_compare,
            "/margin": cmd_margin,
            "/flow": cmd_flow,
        }
        if cmd in mapping:
            await mapping[cmd](message)


@dp.message(Command("summary"))
async def cmd_summary_report(message: types.Message):
    df = load_last_dataframe()
    if df is None:
        return await message.reply("❌ Нет данных. Пришлите CSV/XLS/XLSX.")
    total = len(df)
    miss = lambda col: df[col].isna().sum() / total * 100 if col in df else 0
    stats = {
        "Всего строк": total,
        "% без final_price": miss("final_price"),
        "% без wallet_price": miss("wallet_price"),
        "% без old_price": miss("old_price"),
        "% без price_history": miss("price_history"),
        "% без rating": miss("rating"),
        "% без reviews": miss("reviews"),
    }
    text = "\n".join(f"{k}: {v:.1f} %" for k, v in stats.items())
    await message.reply(f"📊 *Сводка по данным*\n\n{text}", parse_mode="Markdown")


@dp.message(Command("price_hist"))
async def cmd_price_distribution(message: types.Message):
    df = load_last_dataframe()
    if df is None or "price_clean" not in df:
        return await message.reply("❌ Нет поля price_clean.")
    df["price_clean"].dropna().hist(bins=30)
    plt.title("Распределение цен")
    plt.xlabel("Цена"); plt.ylabel("Частота"); plt.grid(alpha=0.3)
    out = REPORTS_DIR / "price_hist.png"
    plt.tight_layout(); plt.savefig(out); plt.close()
    await message.reply_photo(FSInputFile(path=out), caption="📈 Распределение цен")


@dp.message(Command("discount"))
async def cmd_discount_analysis(message: types.Message):
    df = load_last_dataframe()
    if df is None:
        return await message.reply("❌ Нет данных.")
    df = df.copy()
    df["old_num"]   = pd.to_numeric(df.get("old_price", ""), errors="coerce")
    df["final_num"] = pd.to_numeric(df.get("final_price", ""), errors="coerce")
    df["discount_pct"] = (df["old_num"] - df["final_num"]) / df["old_num"] * 100
    df["discount_pct"].dropna().hist(bins=30)
    plt.title("Распределение скидок (%)")
    plt.xlabel("Скидка, %"); plt.ylabel("Частота"); plt.grid(alpha=0.3)
    out = REPORTS_DIR / "discounts.png"
    plt.tight_layout(); plt.savefig(out); plt.close()
    await message.reply_photo(FSInputFile(path=out), caption="💸 Распределение скидок")


@dp.message(Command("chars"))
async def cmd_characteristics_freq(message: types.Message):
    df = load_last_dataframe()
    if df is None or "characteristics_parsed" not in df:
        return await message.reply("❌ Нет поля characteristics_parsed.")
    counter = Counter()
    for props in df["characteristics_parsed"].dropna():
        if isinstance(props, dict):
            counter.update(props.keys())
    text = "\n".join(f"{k}: {v}" for k, v in counter.most_common(15))
    await message.reply(f"📋 *Топ-15 характеристик*\n\n{text}", parse_mode="Markdown")


@dp.message(Command("compare"))
async def cmd_compare(message: types.Message):
    df = load_last_dataframe()
    if df is None or "category" not in df or "price_clean" not in df:
        return await message.reply("❌ Требуются поля category и price_clean.")
    top5 = df.groupby("category")["price_clean"].mean().nlargest(5)
    lines = [f"{i+1}. {cat[:30]}… — {val:.2f}" for i, (cat, val) in enumerate(top5.items())]
    await message.reply(
        "🏷 *Топ-5 категорий по средней цене:*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )


@dp.message(Command("margin"))
async def cmd_margin(message: types.Message):
    df = load_last_dataframe()
    if df is None or "cost" not in df or "price_clean" not in df:
        return await message.reply("❌ Требуются поля cost и price_clean.")
    df = df.copy()
    df["margin_pct"] = (
        df["price_clean"] -
        pd.to_numeric(df["cost"], errors="coerce")
    ) / df["price_clean"] * 100
    df["margin_pct"].dropna().hist(bins=30)
    plt.title("Маржинальность (%)")
    plt.xlabel("Маржа %"); plt.ylabel("Частота"); plt.grid(alpha=0.3)
    out = REPORTS_DIR / "margin.png"
    plt.tight_layout(); plt.savefig(out); plt.close()
    await message.reply_photo(FSInputFile(path=out), caption="📊 Маржинальность")


@dp.message(Command("flow"))
async def cmd_flow(message: types.Message):
    df = load_last_dataframe()
    if df is None or "reviews" not in df or "parsed_at" not in df:
        return await message.reply("❌ Требуются поля reviews и parsed_at.")
    df = df.copy()
    df["date"] = pd.to_datetime(df["parsed_at"], errors="coerce").dt.date
    daily = df.groupby("date")["reviews"].sum()
    plt.figure(figsize=(8, 4))
    daily.plot(marker="o")
    plt.title("Динамика отзывов")
    plt.xlabel("Дата"); plt.ylabel("Сумма reviews"); plt.grid(alpha=0.3)
    out = REPORTS_DIR / "flow.png"
    plt.tight_layout(); plt.savefig(out); plt.close()
    await message.reply_photo(FSInputFile(path=out), caption="📈 Динамика отзывов")
