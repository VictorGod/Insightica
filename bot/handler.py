import asyncio
import logging
import csv
import json
import os
import time
import random
import re
from datetime import datetime
from pathvalidate import sanitize_filename
from hashlib import md5

import requests
from bs4 import BeautifulSoup
from PIL import Image
import pandas as pd
import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from .states import MarketplaceForm
from .config import TG_BOT_TOKEN, get_marketplace_config, get_selenium_config

# Инициализация бота и диспетчера
bot = Bot(token=TG_BOT_TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Директории для хранения данных
DATA_DIR = "marketplace_data"
IMAGES_DIR = os.path.join(DATA_DIR, "images")
CSV_DIR = os.path.join(DATA_DIR, "csv")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

# Создание директорий, если они не существуют
for directory in [DATA_DIR, IMAGES_DIR, CSV_DIR, REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)

# ====================================================
# Функции для обработки характеристик товара
# ====================================================

def parse_characteristics(char_str: str) -> dict:
    """
    Разбирает строку с характеристиками вида "Ключ: значение" (каждая пара с новой строки)
    и возвращает словарь, где значение может быть списком, если встречается разделитель ';'.
    """
    if not char_str:
        return {}
    properties = {}
    lines = char_str.splitlines()
    pattern = re.compile(r'\s*([^:\n]+?)\s*:\s*(.+)$')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            if ";" in value:
                subvalues = [v.strip() for v in value.split(";") if v.strip()]
                properties[key] = subvalues
            else:
                properties[key] = [value]
        else:
            properties[line] = [""]
    return properties

def normalize_characteristics(parsed: dict) -> dict:
    """
    Если список значений содержит один элемент, сохраняет его как строку, иначе оставляет список.
    """
    normalized = {}
    for key, values in parsed.items():
        if len(values) == 1:
            normalized[key] = values[0]
        else:
            normalized[key] = values
    return normalized

def dict_to_str(d: dict) -> str:
    """
    Преобразует словарь в строку, где каждая пара "ключ: значение" записана на новой строке.
    """
    lines = []
    for key, value in d.items():
        if isinstance(value, list):
            value_str = "; ".join(value)
        else:
            value_str = str(value)
        lines.append(f"{key}: {value_str}")
    return "\n".join(lines)


def parse_product_parameters(html: str) -> dict:
    """
    Разбирает HTML блок с таблицами параметров.
    Для каждой таблицы, если есть caption, формирует пару вида "Caption.Ключ": Значение.
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = {}
    tables = soup.find_all("table", class_="product-params__table")
    for table in tables:
        caption = table.find("caption")
        group = caption.get_text(strip=True) if caption else ""
        rows = table.find_all("tr")
        for row in rows:
            th = row.find("th")
            td = row.find("td")
            if th and td:
                key = th.get_text(separator=" ", strip=True)
                value = td.get_text(separator=" ", strip=True)
                if group:
                    result[f"{group}.{key}"] = value
                else:
                    result[key] = value
    return result

# ====================================================
# Функции для работы с веб-страницами
# ====================================================

def get_webdriver():
    """Инициализирует Selenium WebDriver с настройками из config."""
    selenium_config = get_selenium_config()
    chrome_options = Options()
    if selenium_config["headless"]:
        chrome_options.add_argument("--headless")
    user_agent = random.choice(selenium_config["user_agents"])
    chrome_options.add_argument(f"user-agent={user_agent}")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    if selenium_config["proxies"]:
        proxy = random.choice(selenium_config["proxies"])
        chrome_options.add_argument(f"--proxy-server={proxy}")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.set_page_load_timeout(selenium_config["page_load_timeout"])
    return driver

def capture_screenshot(driver, name: str) -> str:
    """Сохраняет скриншот текущей страницы."""
    selenium_config = get_selenium_config()
    screenshots_dir = selenium_config.get("screenshots_dir", "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.png"
    screenshot_path = os.path.join(screenshots_dir, sanitize_filename(filename))
    driver.save_screenshot(screenshot_path)
    return screenshot_path

def save_page_html(driver, name: str) -> str:
    """Сохраняет HTML код страницы и возвращает путь к файлу."""
    html_dir = os.path.join(DATA_DIR, "html_dumps")
    os.makedirs(html_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.html"
    html_path = os.path.join(html_dir, sanitize_filename(filename))
    try:
        page_html = driver.page_source
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page_html)
        meta_data = {
            "url": driver.current_url,
            "timestamp": timestamp,
            "user_agent": driver.execute_script("return navigator.userAgent;"),
            "viewport_size": driver.get_window_size(),
            "page_title": driver.title
        }
        meta_path = html_path.replace('.html', '_meta.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        logger.info(f"HTML страницы сохранён: {html_path}")
        return html_path
    except Exception as e:
        logger.error(f"Ошибка при сохранении HTML: {e}")
        return None

def analyze_page_structure(html_path: str, marketplace: str):
    """Анализирует структуру страницы и сохраняет результат в JSON-файл."""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        config = get_marketplace_config(marketplace)
        selector_analysis = {}
        for selector_name, selector in config.items():
            if isinstance(selector, str) and selector.startswith(('.', '#', '[', 'div')):
                elements = soup.select(selector)
                selector_analysis[selector_name] = {
                    "found": len(elements),
                    "sample": str(elements[0])[:200] if elements else None,
                    "alternative_selectors": find_alternative_selectors(elements[0]) if elements else None
                }
        analysis_path = html_path.replace('.html', '_analysis.json')
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(selector_analysis, f, ensure_ascii=False, indent=2)
        logger.info(f"Анализ структуры страницы сохранён: {analysis_path}")
        missing_selectors = [k for k, v in selector_analysis.items() if v["found"] == 0]
        if missing_selectors:
            logger.warning(f"Не найдены селекторы: {missing_selectors}")
    except Exception as e:
        logger.error(f"Ошибка при анализе структуры страницы: {e}")

def find_alternative_selectors(element) -> list:
    """Находит альтернативные CSS-селекторы для элемента."""
    alternatives = []
    if element:
        if element.get('id'):
            alternatives.append(f"#{element['id']}")
        if element.get('class'):
            alternatives.append(f".{'.'.join(element['class'])}")
        data_attrs = [attr for attr in element.attrs if attr.startswith('data-')]
        for attr in data_attrs:
            alternatives.append(f"[{attr}='{element[attr]}']")
    return alternatives

async def scroll_page(driver, max_scrolls=5):
    """Прокручивает страницу для загрузки динамического контента."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    while scrolls < max_scrolls:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        await asyncio.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scrolls += 1

async def create_price_analysis(message: types.Message, df: pd.DataFrame, category_name: str):
    """Строит графики анализа цен на основе CSV."""
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"price_analysis_{category_name}_{timestamp}.png"
        report_path = os.path.join(REPORTS_DIR, sanitize_filename(report_filename))
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))
        ax1.hist(df['price_clean'], bins=30, alpha=0.7)
        ax1.set_title('Распределение цен')
        ax1.set_xlabel('Цена')
        ax1.set_ylabel('Количество товаров')
        ax1.grid(True, alpha=0.3)
        stats_text = f"""
Минимальная цена: {df['price_clean'].min():,.2f}
Максимальная цена: {df['price_clean'].max():,.2f}
Средняя цена: {df['price_clean'].mean():,.2f}
Медианная цена: {df['price_clean'].median():,.2f}
"""
        ax1.text(0.95, 0.95, stats_text,
                 transform=ax1.transAxes,
                 verticalalignment='top',
                 horizontalalignment='right',
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        ax2.scatter(df['rating'], df['price_clean'], alpha=0.5)
        ax2.set_title('Соотношение цены и рейтинга')
        ax2.set_xlabel('Рейтинг')
        ax2.set_ylabel('Цена')
        ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(report_path, dpi=300, bbox_inches='tight')
        plt.close()
        report_file = FSInputFile(report_path)
        await message.reply_document(
            document=report_file,
            caption="📈 Анализ цен в категории"
        )
    except Exception as e:
        logger.error(f"Ошибка при создании анализа цен: {e}")
        await message.reply("❌ Не удалось создать анализ цен")

async def check_selectors_validity():
    """Периодически проверяет валидность CSS-селекторов."""
    while True:
        try:
            for marketplace in ["ozon", "wb"]:
                config = get_marketplace_config(marketplace)
                driver = get_webdriver()
                try:
                    driver.get(config["test_url"])
                    await asyncio.sleep(5)
                    html_path = save_page_html(driver, f"{marketplace}_test_page")
                    if html_path:
                        analyze_page_structure(html_path, marketplace)
                finally:
                    driver.quit()
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Ошибка при проверке селекторов: {e}")
            await asyncio.sleep(300)

def marketplace_keyboard():
    """Создаёт клавиатуру для выбора действия ботом."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Парсинг категории Wildberries", callback_data="parse_wb_category")],
        [InlineKeyboardButton(text="Парсинг категории Ozon", callback_data="parse_ozon_category")],
        [InlineKeyboardButton(text="Информация о товаре WB", callback_data="parse_wb_product")],
        [InlineKeyboardButton(text="Информация о товаре Ozon", callback_data="parse_ozon_product")],
        [InlineKeyboardButton(text="Анализ цен из CSV", callback_data="analyze_prices")],
        [InlineKeyboardButton(text="Мониторинг цен", callback_data="price_monitoring")],
        [InlineKeyboardButton(text="Помощь", callback_data="help")]
    ])
    return kb

def get_full_product_info(product_url, marketplace):
    """
    Получает детальную информацию о товаре.
    Для Wildberries после загрузки страницы кликается по кнопке "Характеристики и описание",
    и дополнительно извлекается структурированная информация из popup.
    Полное описание собирается из блока основной страницы и из popup (если доступно).
    """
    info = {}
    max_attempts = 3
    attempt = 0
    driver = get_webdriver()
    while attempt < max_attempts:
        try:
            driver.get(product_url)
            time.sleep(5)  # Ждём загрузку контента
            if "Доступ ограничен" in driver.title:
                logger.warning("Доступ ограничен, повторная попытка...")
                attempt += 1
                time.sleep(5)
                continue
            else:
                break
        except Exception as e:
            logger.error(f"Ошибка загрузки страницы товара: {e}")
            attempt += 1
            time.sleep(5)
    if attempt == max_attempts:
        logger.error("Не удалось загрузить страницу товара после нескольких попыток")
        driver.quit()
        return info

    detail_screenshot = capture_screenshot(driver, "product_detail_page")
    logger.info(f"Скриншот товара сохранён: {detail_screenshot}")
    detail_html = save_page_html(driver, "product_detail_page")
    if detail_html:
        analyze_page_structure(detail_html, marketplace)
    config = get_marketplace_config(marketplace)
    details = config.get("product_detail", {
        "title": "h1.product-page__title",
        "price": "ins.price-block__final-price.wallet",
        "description": "div.product-page__description",
        "images": "div.product-page__gallery img",
        "characteristics": "div.product-params",
        "parameters_selector": "div.product-params",
        "reviews_container": "div.product-page__reviews"
    })
    try:
        info["full_title"] = driver.find_element(By.CSS_SELECTOR, details["title"]).text
    except Exception as e:
        info["full_title"] = ""
    try:
        if marketplace.lower() == "wb":
            price_elem = driver.find_element(By.CSS_SELECTOR, details["price"])
            info["final_price"] = price_elem.text.strip()
            try:
                wallet_elem = driver.find_element(By.CSS_SELECTOR, "span.price-block__wallet-price.red-price")
                info["wallet_price"] = wallet_elem.text.strip()
            except:
                info["wallet_price"] = ""
            try:
                old_price_elem = driver.find_element(By.CSS_SELECTOR, "del.price-block__old-price span")
                info["old_price"] = old_price_elem.text.strip()
            except:
                info["old_price"] = ""
            try:
                price_history_btn = driver.find_element(By.CSS_SELECTOR, "button.price-history__btn")
                driver.execute_script("arguments[0].click();", price_history_btn)
                time.sleep(2)
                popup = driver.find_element(By.CSS_SELECTOR, "div.popup-history-price.shown")
                history_price = popup.find_element(By.CSS_SELECTOR, "h2.price-history__title").text.strip()
                range_text = popup.find_element(By.CSS_SELECTOR, "p.price-history__text").text.strip()
                info["price_history"] = {"current": history_price, "range": range_text}
                try:
                    close_btn = popup.find_element(By.CSS_SELECTOR, "a.j-close")
                    close_btn.click()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Не удалось получить историю цены: {e}")
        else:
            price_elem = driver.find_element(By.CSS_SELECTOR, details["price"])
            info["full_price"] = price_elem.text.strip()
    except Exception as e:
        logger.error(f"Ошибка при получении цены: {e}")
        info["final_price"] = ""
    try:
        # Берем полное описание с основной страницы
        main_description = driver.find_element(By.CSS_SELECTOR, details["description"]).text.strip()
        info["description"] = main_description
    except:
        info["description"] = ""
    try:
        image_elements = driver.find_elements(By.CSS_SELECTOR, details["images"])
        info["detail_images"] = [img.get_attribute("src") for img in image_elements]
    except:
        info["detail_images"] = []
    try:
        raw_chars = driver.find_element(By.CSS_SELECTOR, details["characteristics"]).text
        info["characteristics"] = raw_chars  # Сохраняем в одном столбце
        info["characteristics_parsed"] = normalize_characteristics(parse_characteristics(raw_chars))
    except Exception as e:
        info["characteristics"] = ""
        info["characteristics_parsed"] = {}
    try:
        info["detail_reviews"] = driver.find_element(By.CSS_SELECTOR, details["reviews_container"]).text
    except:
        info["detail_reviews"] = ""
    
    # Для Wildberries дополнительно получаем параметры и описание из popup
    if marketplace.lower() == "wb":
        try:
            detail_button = driver.find_element(By.CSS_SELECTOR, "button.product-page__btn-detail.j-details-btn-desktop")
            driver.execute_script("arguments[0].click();", detail_button)
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.popup-product-details.shown"))
            )
            popup = driver.find_element(By.CSS_SELECTOR, "div.popup-product-details.shown")
            try:
                parameters_element = popup.find_element(By.CSS_SELECTOR, details["parameters_selector"])
                parameters_html = parameters_element.get_attribute("outerHTML")
                info["parameters"] = parse_product_parameters(parameters_html)
            except Exception as pe:
                logger.warning("Не удалось получить блок параметров из popup: " + str(pe))
                info["parameters"] = {}
            try:
                # Берем полное описание из popup, без разделения по заголовку "Описание"
                popup_description = popup.find_element(By.CSS_SELECTOR, "section.product-details__description").text.strip()
                # Объединяем с основной информацией (если уже есть)
                if info.get("description"):
                    info["description"] = f"{info['description']}\n{popup_description}"
                else:
                    info["description"] = popup_description
            except Exception as de:
                logger.warning("Не удалось получить описание из popup: " + str(de))
        except Exception as e:
            logger.warning("Не удалось получить подробную информацию из popup: " + str(e))
    
    driver.quit()
    return info

# ====================================================
# Функции для пагинации и динамического скроллинга (Wildberries)
# ====================================================

def update_page_param(url, page):
    """
    Обновляет или добавляет параметр 'page' в URL.
    """
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    query['page'] = [str(page)]
    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))

def scroll_until_no_new_elements(driver, config, product_selector):
    """
    Прокручивает страницу до тех пор, пока новые элементы не перестанут подгружаться.
    """
    scroll_pause = config.get("scroll_pause", 2)
    max_attempts = config.get("max_scroll_attempts", 5)
    attempts = 0
    previous_count = len(driver.find_elements(By.CSS_SELECTOR, product_selector))
    while attempts < max_attempts:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause)
        current_elements = driver.find_elements(By.CSS_SELECTOR, product_selector)
        current_count = len(current_elements)
        if current_count > previous_count:
            previous_count = current_count
            attempts = 0
        else:
            attempts += 1
    return driver.find_elements(By.CSS_SELECTOR, product_selector)

def parse_wb_category_by_pagination(category_url, target_count):
    """
    Последовательно парсит категорию Wildberries с переходом по страницам (клик по "Следующая страница").
    Собирает карточки товаров, затем получает детальную информацию для каждого товара.
    """
    config = get_marketplace_config("wb")
    driver = get_webdriver()
    products = []
    try:
        driver.get(category_url)
        time.sleep(5)
        while len(products) < target_count:
            try:
                driver.execute_script(config["scroll_script"])
            except Exception as e:
                logger.warning(f"Ошибка скрипта прокрутки: {e}")
            scroll_until_no_new_elements(driver, config, config["product_card_selector"])
            product_elements = driver.find_elements(By.CSS_SELECTOR, config["product_card_selector"])
            if product_elements:
                for element in product_elements:
                    try:
                        title = element.find_element(By.CSS_SELECTOR, config["title_selector"]).text
                    except Exception:
                        title = "Без названия"
                    try:
                        product_url = element.find_element(By.CSS_SELECTOR, config["link_selector"]).get_attribute("href")
                    except Exception:
                        product_url = ""
                    try:
                        price_element = element.find_element(By.CSS_SELECTOR, config["price_selector"])
                        price = price_element.text.strip()
                        price_clean = re.sub(r'[^\d.]', '', price)
                    except Exception:
                        price = "Нет в наличии"
                        price_clean = "0"
                    product = {
                        "title": title,
                        "price": price,
                        "price_clean": float(price_clean) if price_clean else 0,
                        "url": product_url,
                        "marketplace": "wildberries",
                        "category_url": category_url,
                        "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    products.append(product)
                    if len(products) >= target_count:
                        break
            else:
                logger.info("На странице не найдены карточки товаров.")
            logger.info(f"Обработано страниц, собрано товаров: {len(products)}")
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, config.get("pagination_next_selector", "a.pagination-next.j-next-page"))
                if next_button:
                    logger.info("Переход на следующую страницу через пагинацию.")
                    next_button.click()
                    time.sleep(5)
                else:
                    logger.info("Кнопка 'Следующая страница' не найдена, завершаем парсинг.")
                    break
            except Exception as e:
                logger.error(f"Ошибка при переходе на следующую страницу: {e}")
                break
    finally:
        driver.quit()
    detailed_products = []
    for product in products:
        if product.get("url"):
            full_info = asyncio.run(asyncio.to_thread(get_full_product_info, product["url"], "wb"))
            product.update(full_info)
        detailed_products.append(product)
    return detailed_products

def parse_wb_category_parallel(category_url, target_pages, target_count_per_page):
    """
    Параллельный парсинг категории Wildberries по номерам страниц.
    Извлекаются ссылки на страницы, затем для каждой страницы запускается обработка.
    """
    config = get_marketplace_config("wb")
    driver = get_webdriver()
    driver.get(category_url)
    time.sleep(5)
    pagination_links = {}
    try:
        pagination_elements = driver.find_elements(By.CSS_SELECTOR, config.get("pagination_numbers_selector", "a.pagination-item.j-page"))
        for elem in pagination_elements:
            try:
                page_num = int(elem.text.strip())
                href = elem.get_attribute("href")
                pagination_links[page_num] = href
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Ошибка извлечения пагинации: {e}")
    driver.quit()
    selected_page_urls = [pagination_links[p] for p in target_pages if p in pagination_links and pagination_links[p]]
    logger.info(f"Выбраны страницы для параллельного запуска: {selected_page_urls}")
    all_products = []
    import concurrent.futures
    def process_page(url):
        products = []
        local_driver = get_webdriver()
        try:
            local_driver.get(url)
            time.sleep(5)
            try:
                local_driver.execute_script(config["scroll_script"])
            except Exception as e:
                logger.warning(f"Ошибка скрипта прокрутки: {e}")
            scroll_until_no_new_elements(local_driver, config, config["product_card_selector"])
            product_elements = local_driver.find_elements(By.CSS_SELECTOR, config["product_card_selector"])
            for element in product_elements:
                try:
                    title = element.find_element(By.CSS_SELECTOR, config["title_selector"]).text
                except Exception:
                    title = "Без названия"
                try:
                    product_url = element.find_element(By.CSS_SELECTOR, config["link_selector"]).get_attribute("href")
                except Exception:
                    product_url = ""
                try:
                    price_element = element.find_element(By.CSS_SELECTOR, config["price_selector"])
                    price = price_element.text.strip()
                    price_clean = re.sub(r'[^\d.]', '', price)
                except Exception:
                    price = "Нет в наличии"
                    price_clean = "0"
                product = {
                    "title": title,
                    "price": price,
                    "price_clean": float(price_clean) if price_clean else 0,
                    "url": product_url,
                    "marketplace": "wildberries",
                    "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                products.append(product)
                if len(products) >= target_count_per_page:
                    break
        except Exception as e:
            logger.error(f"Ошибка обработки страницы {url}: {e}")
        finally:
            local_driver.quit()
        return products
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected_page_urls)) as executor:
        futures = [executor.submit(process_page, url) for url in selected_page_urls]
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                all_products.extend(res)
            except Exception as e:
                logger.error(f"Ошибка параллельного запуска: {e}")
    detailed_products = []
    for product in all_products:
        if product.get("url"):
            full_info = asyncio.run(asyncio.to_thread(get_full_product_info, product["url"], "wb"))
            product.update(full_info)
        detailed_products.append(product)
    return detailed_products

# ====================================================
# Обработчики команд и состояний
# ====================================================

@dp.message(Command("start"))
async def handle_start(message: types.Message):
    start_message = (
        "👋 Привет! Я бот для парсинга маркетплейсов. Вот что я умею:\n\n"
        "📊 Парсинг категорий товаров с Wildberries и Ozon\n"
        "🔍 Получение детальной информации о товарах\n"
        "📈 Анализ цен и создание отчетов\n"
        "⏱ Мониторинг изменения цен\n\n"
        "Выберите действие из меню ниже:"
    )
    await message.answer(start_message, reply_markup=marketplace_keyboard())

@dp.message(Command("help"))
async def handle_help(message: types.Message):
    help_message = (
        "📚 **Справка по использованию бота**\n\n"
        "Бот позволяет парсить данные с маркетплейсов Wildberries и Ozon.\n\n"
        "**Основные команды:**\n"
        "/start - Запустить бота и показать главное меню\n"
        "/help - Показать эту справку\n\n"
        "**Доступные функции:**\n"
        "• Парсинг категории Wildberries\n"
        "• Парсинг категории Ozon\n"
        "• Получение детальной информации о товаре\n"
        "• Анализ цен\n"
        "• Мониторинг цен\n\n"
        "Для начала работы нажмите на соответствующую кнопку в меню."
    )
    await message.answer(help_message)

@dp.callback_query(lambda c: c.data == 'parse_ozon_category')
async def handle_parse_ozon_category(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer(
        "Пожалуйста, отправьте ссылку на категорию товаров в Ozon\n"
        "Пример: https://www.ozon.ru/category/smartfony-15502/"
    )
    await state.set_state(MarketplaceForm.waiting_for_ozon_category_url)
    await callback_query.answer()

@dp.message(MarketplaceForm.waiting_for_ozon_category_url)
async def process_ozon_category_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if "ozon.ru/category" not in url and "ozon.ru/brand" not in url:
        await message.reply(
            "Пожалуйста, отправьте корректную ссылку на категорию товаров Ozon\n"
            "Пример: https://www.ozon.ru/category/smartfony-15502/"
        )
        return
    try:
        processing_msg = await message.reply("⏳ Начинаю обработку категории...")
        config = get_marketplace_config("ozon")
        driver = get_webdriver()
        try:
            driver.get(url)
            await asyncio.sleep(5)
            screenshot_path = capture_screenshot(driver, "ozon_category_page")
            logger.info(f"Скриншот сохранён: {screenshot_path}")
            html_path = save_page_html(driver, "ozon_category_page")
            if html_path:
                analyze_page_structure(html_path, "ozon")
            await scroll_page(driver)
            products = []
            product_elements = driver.find_elements(By.CSS_SELECTOR, config["product_card_selector"])
            if not product_elements:
                await message.reply("❌ Товары не найдены")
                return
            await message.reply(f"📝 Найдено товаров: {len(product_elements)}")
            for i, element in enumerate(product_elements[:50]):
                try:
                    title = element.find_element(By.CSS_SELECTOR, config["title_selector"]).text
                    try:
                        price_element = element.find_element(By.CSS_SELECTOR, config["price_selector"])
                        price = price_element.text.strip()
                        price_clean = re.sub(r'[^\d.]', '', price)
                    except:
                        price = "Нет в наличии"
                        price_clean = "0"
                    try:
                        product_url = element.find_element(By.CSS_SELECTOR, config["link_selector"]).get_attribute("href")
                    except Exception as e:
                        logger.warning("Основной селектор ссылки не сработал")
                        try:
                            product_url = element.find_elements(By.TAG_NAME, "a")[0].get_attribute("href")
                        except Exception as ex:
                            product_url = ""
                    try:
                        image_url = element.find_element(By.CSS_SELECTOR, config["image_selector"]).get_attribute("src")
                    except:
                        image_url = ""
                    try:
                        rating_element = element.find_element(By.CSS_SELECTOR, config["rating_selector"])
                        rating = float(re.search(r'width:\s*(\d+)%', rating_element.get_attribute("style")).group(1)) / 20
                    except:
                        rating = 0
                    try:
                        reviews = element.find_element(By.CSS_SELECTOR, config["reviews_selector"]).text
                        reviews = int(re.sub(r'[^\d]', '', reviews))
                    except:
                        reviews = 0
                    product = {
                        "title": title,
                        "price": price,
                        "price_clean": float(price_clean) if price_clean else 0,
                        "url": product_url,
                        "image_url": image_url,
                        "rating": rating,
                        "reviews": reviews,
                        "marketplace": "ozon",
                        "category_url": url,
                        "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    products.append(product)
                    if (i+1) % 10 == 0:
                        await message.reply(f"⏳ Обработано товаров: {i+1}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке товара: {e}")
                    continue
            for product in products:
                if product.get("url"):
                    full_info = await asyncio.to_thread(get_full_product_info, product["url"], "ozon")
                    product.update(full_info)
            if products:
                category_name = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                excel_filename = f"ozon_{category_name}_{timestamp}.xlsx"
                excel_path = os.path.join(CSV_DIR, sanitize_filename(excel_filename))
                df = pd.DataFrame(products)
                # Для Ozon не проводим разбиение столбца characteristics на столбцы
                with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False)
                excel_file = FSInputFile(excel_path)
                await message.reply_document(
                    document=excel_file,
                    caption=f"📊 Результаты парсинга категории Ozon ({len(products)} товаров)"
                )
                await create_price_analysis(message, df, category_name)
            await message.reply("✅ Обработка категории завершена!")
        finally:
            driver.quit()
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка обработки категории: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
        await state.clear()

@dp.callback_query(lambda c: c.data == 'parse_wb_category')
async def handle_parse_wb_category(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer(
        "Пожалуйста, отправьте ссылку на категорию Wildberries\n"
        "Пример: https://www.wildberries.ru/catalog/elektronika/smartfony-i-telefony"
    )
    await state.set_state(MarketplaceForm.waiting_for_wb_category_url)
    await callback_query.answer()

@dp.message(MarketplaceForm.waiting_for_wb_category_url)
async def process_wb_category_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if "wildberries.ru/catalog" not in url:
        await message.reply(
            "Введите корректную ссылку на категорию Wildberries\n"
            "Пример: https://www.wildberries.ru/catalog/elektronika/smartfony-i-telefony"
        )
        return
    await state.update_data(category_url=url)
    await message.reply("Введите количество товаров для парсинга (например, 1300):")
    await state.set_state(MarketplaceForm.waiting_for_item_count)

@dp.message(MarketplaceForm.waiting_for_item_count)
async def process_item_count(message: types.Message, state: FSMContext):
    try:
        target_count = int(message.text.strip())
        if target_count <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Введите положительное число.")
        return
    await state.update_data(target_count=target_count)
    await message.reply("⏳ Начинаю обработку категории Wildberries...")
    data = await state.get_data()
    category_url = data.get("category_url")
    products = await asyncio.to_thread(parse_wb_category_by_pagination, category_url, target_count)
    if products:
        category_name = category_url.rstrip('/').split('/')[-1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f"wb_{category_name}_{timestamp}.xlsx"
        excel_path = os.path.join(CSV_DIR, sanitize_filename(excel_filename))
        df = pd.DataFrame(products)
        # Если присутствует колонка "parameters", разворачиваем её в отдельные столбцы с MultiIndex
        if "parameters" in df.columns:
            params_df = df["parameters"].apply(lambda x: pd.Series(x) if isinstance(x, dict) else pd.Series())
            tuples = [tuple(col.split(".", 1)) if "." in col else ("", col) for col in params_df.columns]
            params_df.columns = pd.MultiIndex.from_tuples(tuples)
            df = pd.concat([df.drop(columns=["parameters"]), params_df], axis=1)
        with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        excel_file = FSInputFile(excel_path)
        await message.reply_document(
            document=excel_file,
            caption=f"📊 Результаты парсинга Wildberries ({len(products)} товаров)"
        )
        await message.reply("✅ Обработка завершена!")
    else:
        await message.reply("❌ Товары не собраны.")
    await state.clear()

@dp.callback_query(lambda c: c.data == 'parse_wb_product')
async def handle_parse_wb_product(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Пожалуйста, отправьте ссылку на товар Wildberries:")
    await state.set_state(MarketplaceForm.waiting_for_wb_product_url)
    await callback_query.answer()

@dp.message(MarketplaceForm.waiting_for_wb_product_url)
async def process_wb_product_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    try:
        processing_msg = await message.reply("⏳ Получаю информацию о товаре...")
        full_info = await asyncio.to_thread(get_full_product_info, url, "wb")
        response_text = f"Детальная информация о товаре:\n{json.dumps(full_info, ensure_ascii=False, indent=2)}"
        await message.reply(response_text)
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка получения товара: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
        await state.clear()

@dp.callback_query(lambda c: c.data == 'parse_ozon_product')
async def handle_parse_ozon_product(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Пожалуйста, отправьте ссылку на товар Ozon:")
    await state.set_state(MarketplaceForm.waiting_for_ozon_product_url)
    await callback_query.answer()

@dp.message(MarketplaceForm.waiting_for_ozon_product_url)
async def process_ozon_product_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    try:
        processing_msg = await message.reply("⏳ Получаю информацию о товаре...")
        full_info = await asyncio.to_thread(get_full_product_info, url, "ozon")
        response_text = f"Детальная информация о товаре:\n{json.dumps(full_info, ensure_ascii=False, indent=2)}"
        await message.reply(response_text)
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка получения товара: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
        await state.clear()

@dp.callback_query(lambda c: c.data == 'analyze_prices')
async def handle_analyze_prices(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Эта функция использует CSV для анализа цен. (Реализация зависит от CSV)")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == 'price_monitoring')
async def handle_price_monitoring(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Эта функция позволяет настроить мониторинг цен. (Реализация зависит от проекта)")
    await callback_query.answer()
