import asyncio
import logging
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from ..services.parsers import parse_characteristics, normalize_characteristics, parse_product_parameters
from ..services.selenium_utils import (
    capture_screenshot,
    save_page_html,
    analyze_page_structure,
    get_webdriver,
    scroll_page                
)
from ..config import get_marketplace_config

logger = logging.getLogger(__name__)

def flatten_dict(d: dict, parent_key: str = '', sep: str = ': ') -> dict:
    """
    Рекурсивно распаковывает вложенные словари в плоский словарь.
    Ключи объединяются через разделитель sep.
    """
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


def get_full_product_info(product_url: str, marketplace: str) -> dict:
    info = {}
    cfg = get_marketplace_config(marketplace)
    driver = get_webdriver()

    # Попытки загрузить страницу, если «Доступ ограничен»
    for _ in range(3):
        try:
            driver.get(product_url)
            time.sleep(5)
            if 'Доступ ограничен' in driver.title:
                logger.warning('Доступ ограничен, повторяю попытку...')
                time.sleep(5)
                continue
            break
        except Exception as e:
            logger.error(f'Ошибка при загрузке страницы: {e}')
            time.sleep(5)
    else:
        driver.quit()
        return info

    # Снимок и дамп HTML
    capture_screenshot(driver, 'ozon_product')
    html_path = save_page_html(driver, 'ozon_product')
    if html_path:
        analyze_page_structure(html_path, marketplace)

    details = cfg.get('product_detail', {})

    # Основные поля
    try:
        info['full_title'] = driver.find_element(By.CSS_SELECTOR, details.get('title','')).text.strip()
    except:
        info['full_title'] = ''
    try:
        info['final_price'] = driver.find_element(By.CSS_SELECTOR, details.get('price','')).text.strip()
    except:
        info['final_price'] = ''
    try:
        info['wallet_price'] = driver.find_element(By.CSS_SELECTOR, 'span.price-block__wallet-price.red-price').text.strip()
    except:
        info['wallet_price'] = ''
    try:
        info['old_price'] = driver.find_element(By.CSS_SELECTOR, 'del.price-block__old-price span').text.strip()
    except:
        info['old_price'] = ''

    # Описание
    try:
        info['description'] = driver.find_element(By.CSS_SELECTOR, details.get('description','')).text.strip()
    except:
        info['description'] = ''

    # Изображения
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, details.get('images',''))
        info['detail_images'] = [img.get_attribute('src') for img in imgs]
    except:
        info['detail_images'] = []

    # Характеристики: парсинг, нормализация, распаковка
    try:
        raw = driver.find_element(By.CSS_SELECTOR, details.get('characteristics','')).text
        parsed = parse_characteristics(raw)
        normalized = normalize_characteristics(parsed)
        # Плоский словарь характеристик
        flat_chars = flatten_dict(normalized)
        info['characteristics_parsed'] = normalized
        info['extracted_characteristics'] = flat_chars
        # Добавляем каждую характеристику как отдельное поле
        for header, value in flat_chars.items():
            key = re.sub(r"\W+", "_", header).strip('_').lower()
            info[key] = value
    except Exception:
        info['characteristics_parsed'] = {}
        info['extracted_characteristics'] = {}

    # Дополнительные параметры из попапа
    if marketplace.lower() == 'ozon':
        try:
            btn = driver.find_element(By.CSS_SELECTOR, 'button.product-page__btn-detail.j-details-btn-desktop')
            driver.execute_script('arguments[0].click();', btn)
            WebDriverWait(driver,10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR,'div.popup-product-details.shown'))
            )
            popup = driver.find_element(By.CSS_SELECTOR,'div.popup-product-details.shown')
            html_params = popup.find_element(By.CSS_SELECTOR, details.get('parameters_selector','')).get_attribute('outerHTML')
            params = parse_product_parameters(html_params)
            # Распаковываем параметры
            flat_params = flatten_dict(params)
            info['parameters'] = params
            info['extracted_parameters'] = flat_params
            for header, value in flat_params.items():
                key = re.sub(r"\W+", "_", header).strip('_').lower()
                info[key] = value
        except Exception:
            info['parameters'] = {}
            info['extracted_parameters'] = {}

    driver.quit()
    return info


def parse_ozon_category(category_url: str, target_count: int) -> list:
    cfg = get_marketplace_config('ozon')
    driver = get_webdriver()
    products = []
    try:
        driver.get(category_url)
        time.sleep(5)
        capture_screenshot(driver,'ozon_category')
        html_path = save_page_html(driver,'ozon_category')
        if html_path:
            analyze_page_structure(html_path,'ozon')
        asyncio.run(scroll_page(driver))
        cards = driver.find_elements(By.CSS_SELECTOR,cfg['product_card_selector'])
        for card in cards[:target_count]:
            try:
                title = card.find_element(By.CSS_SELECTOR,cfg['title_selector']).text
            except:
                title = ''
            try:
                price_txt = card.find_element(By.CSS_SELECTOR,cfg['price_selector']).text
                price_clean = float(re.sub(r'[^\d.]','',price_txt) or 0)
            except:
                price_txt, price_clean = '',''
            try:
                url = card.find_element(By.CSS_SELECTOR,cfg['link_selector']).get_attribute('href')
            except:
                url = ''
            products.append({
                'title': title,
                'price': price_txt,
                'price_clean': price_clean,
                'url': url,
            })
    finally:
        driver.quit()
    detailed = []
    for p in products:
        if p.get('url'):
            info = asyncio.run(asyncio.to_thread(get_full_product_info,p['url'],'ozon'))
            p.update(info)
        detailed.append(p)
    return detailed
