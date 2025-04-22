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

def get_full_product_info(product_url: str, marketplace: str) -> dict:
    info = {}
    cfg = get_marketplace_config(marketplace)
    driver = get_webdriver()

    # Попытки загрузить страницу, если «Доступ ограничен»
    for _ in range(3):
        try:
            driver.get(product_url)
            time.sleep(5)
            if "Доступ ограничен" in driver.title:
                logger.warning("Доступ ограничен, повторяю попытку...")
                time.sleep(5)
                continue
            break
        except Exception as e:
            logger.error(f"Ошибка при загрузке страницы: {e}")
            time.sleep(5)
    else:
        driver.quit()
        return info

    # Снимок и дамп HTML
    screenshot_path = capture_screenshot(driver, "ozon_product")
    logger.info(f"Скриншот товара сохранен: {screenshot_path}")
    
    html_path = save_page_html(driver, "ozon_product")
    if html_path:
        logger.info(f"HTML товара сохранен: {html_path}")
        analyze_page_structure(html_path, marketplace)

    details = cfg.get("product_detail", {})

    # Заголовок
    try:
        info["full_title"] = driver.find_element(By.CSS_SELECTOR, details.get("title", "")).text.strip()
        logger.debug(f"Найдено название: {info['full_title']}")
    except Exception as e:
        info["full_title"] = ""
        logger.debug(f"Ошибка получения названия: {e}")

    # Цена и бонусы
    try:
        info["final_price"] = driver.find_element(By.CSS_SELECTOR, details.get("price", "")).text.strip()
        logger.debug(f"Найдена цена: {info['final_price']}")
    except Exception as e:
        info["final_price"] = ""
        logger.debug(f"Ошибка получения цены: {e}")
        
    try:
        info["wallet_price"] = driver.find_element(By.CSS_SELECTOR, "span.price-block__wallet-price.red-price").text.strip()
        logger.debug(f"Найдена цена по карте: {info['wallet_price']}")
    except Exception as e:
        info["wallet_price"] = ""
        logger.debug(f"Ошибка получения цены по карте: {e}")
        
    try:
        info["old_price"] = driver.find_element(By.CSS_SELECTOR, "del.price-block__old-price span").text.strip()
        logger.debug(f"Найдена старая цена: {info['old_price']}")
    except Exception as e:
        info["old_price"] = ""
        logger.debug(f"Ошибка получения старой цены: {e}")

    # История цены (вызываем popup)
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button.price-history__btn")
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(2)
        popup = driver.find_element(By.CSS_SELECTOR, "div.popup-history-price.shown")
        info["price_history"] = {
            "current": popup.find_element(By.CSS_SELECTOR, "h2.price-history__title").text.strip(),
            "range":   popup.find_element(By.CSS_SELECTOR, "p.price-history__text").text.strip()
        }
        logger.debug(f"Найдена история цен: {info['price_history']}")
        try:
            popup.find_element(By.CSS_SELECTOR, "a.j-close").click()
        except:
            pass
    except Exception as e:
        info["price_history"] = {}
        logger.debug(f"Нет истории цен: {e}")

    # Описание
    try:
        info["description"] = driver.find_element(By.CSS_SELECTOR, details.get("description", "")).text.strip()
        logger.debug("Найдено описание")
    except Exception as e:
        info["description"] = ""
        logger.debug(f"Ошибка получения описания: {e}")

    # Изображения
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, details.get("images", ""))
        info["detail_images"] = [i.get_attribute("src") for i in imgs]
        logger.debug(f"Найдено изображений: {len(info['detail_images'])}")
    except Exception as e:
        info["detail_images"] = []
        logger.debug(f"Ошибка получения изображений: {e}")

    # Характеристики
    try:
        raw = driver.find_element(By.CSS_SELECTOR, details.get("characteristics", "")).text
        info["characteristics"] = raw
        parsed = parse_characteristics(raw)
        info["characteristics_parsed"] = normalize_characteristics(parsed)
        logger.debug("Найдены характеристики")
    except Exception as e:
        info["characteristics"] = ""
        info["characteristics_parsed"] = {}
        logger.debug(f"Ошибка получения характеристик: {e}")

    # Ozon‑popup с дополнительными параметрами
    if marketplace.lower() == "ozon":
        try:
            detail_btn = driver.find_element(By.CSS_SELECTOR, "button.product-page__btn-detail.j-details-btn-desktop")
            driver.execute_script("arguments[0].click();", detail_btn)
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.popup-product-details.shown"))
            )
            popup = driver.find_element(By.CSS_SELECTOR, "div.popup-product-details.shown")
            # Параметры
            try:
                html_params = popup.find_element(By.CSS_SELECTOR, details.get("parameters_selector", "")).get_attribute("outerHTML")
                info["parameters"] = parse_product_parameters(html_params)
                logger.debug("Найдены дополнительные параметры")
            except Exception as e:
                info["parameters"] = {}
                logger.debug(f"Ошибка получения дополнительных параметров: {e}")
            # Доп. описание
            try:
                ext = popup.find_element(By.CSS_SELECTOR, "section.product-details__description").text.strip()
                info["description"] = f"{info.get('description','')}\n{ext}"
                logger.debug("Найдено дополнительное описание")
            except Exception as e:
                logger.debug(f"Ошибка получения дополнительного описания: {e}")
        except Exception as e:
            logger.debug(f"Нет popup‑блока деталей: {e}")

    driver.quit()
    return info

def parse_ozon_category(category_url: str, target_count: int) -> list:
    cfg = get_marketplace_config("ozon")
    driver = get_webdriver()
    products = []

    try:
        logger.info(f"Загрузка страницы: {category_url}")
        driver.get(category_url)
        time.sleep(5)
        
        # Сделаем скриншот для отладки
        screenshot_path = capture_screenshot(driver, "ozon_category")
        logger.info(f"Скриншот сохранен: {screenshot_path}")
        
        # Сохраним HTML для анализа
        html_path = save_page_html(driver, "ozon_category")
        if html_path:
            logger.info(f"HTML сохранен: {html_path}")
            analyze_page_structure(html_path, "ozon")

        logger.info("Начинаем прокрутку страницы...")
        asyncio.run(scroll_page(driver))
        
        # Найдем все карточки
        cards = driver.find_elements(By.CSS_SELECTOR, cfg["product_card_selector"])
        logger.info(f"Найдено карточек товаров на странице: {len(cards)}")
        
        # Сделаем еще один скриншот после прокрутки
        screenshot_path = capture_screenshot(driver, "ozon_category_scrolled")
        logger.info(f"Скриншот после прокрутки: {screenshot_path}")

        for i, card in enumerate(cards[:target_count], 1):
            try:
                title = card.find_element(By.CSS_SELECTOR, cfg["title_selector"]).text
                logger.debug(f"Товар {i}: Название найдено")
            except Exception as e:
                title = ""
                logger.debug(f"Товар {i}: Ошибка получения названия: {e}")
                
            try:
                price_txt = card.find_element(By.CSS_SELECTOR, cfg["price_selector"]).text
                price_clean = float(re.sub(r"[^\d.]","", price_txt) or 0)
                logger.debug(f"Товар {i}: Цена найдена: {price_txt}")
            except Exception as e:
                price_txt = ""
                price_clean = 0.0
                logger.debug(f"Товар {i}: Ошибка получения цены: {e}")
                
            try:
                url = card.find_element(By.CSS_SELECTOR, cfg["link_selector"]).get_attribute("href")
                logger.debug(f"Товар {i}: URL найден: {url}")
            except Exception as e:
                url = ""
                logger.debug(f"Товар {i}: Ошибка получения URL: {e}")

            products.append({
                "title": title,
                "price": price_txt,
                "price_clean": price_clean,
                "url": url,
            })
            logger.info(f"Обработан товар {i}/{min(len(cards), target_count)}")
    except Exception as e:
        logger.error(f"Ошибка при парсинге категории: {e}")
        logger.error(f"Текущий URL: {driver.current_url}")
        screenshot_path = capture_screenshot(driver, "ozon_category_error")
        logger.error(f"Скриншот ошибки: {screenshot_path}")
    finally:
        driver.quit()

    logger.info(f"Начинаем сбор детальной информации для {len(products)} товаров")
    detailed = []
    for i, p in enumerate(products, 1):
        if p["url"]:
            logger.info(f"Получение детальной информации для товара {i}/{len(products)}: {p['url']}")
            try:
                info = asyncio.run(asyncio.to_thread(get_full_product_info, p["url"], "ozon"))
                p.update(info)
                logger.info(f"Детальная информация получена для товара {i}")
            except Exception as e:
                logger.error(f"Ошибка при получении детальной информации для {p['url']}: {e}")
        detailed.append(p)
    
    logger.info(f"Парсинг завершен. Всего обработано товаров: {len(detailed)}")
    return detailed