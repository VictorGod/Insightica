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
    capture_screenshot(driver, "wb_product")
    html_path = save_page_html(driver, "wb_product")
    if html_path:
        analyze_page_structure(html_path, marketplace)

    details = cfg.get("product_detail", {})

    # Заголовок
    try:
        info["full_title"] = driver.find_element(By.CSS_SELECTOR, details.get("title", "")).text.strip()
    except:
        info["full_title"] = ""

    # Цена и бонусы
    try:
        info["final_price"] = driver.find_element(By.CSS_SELECTOR, details.get("price", "")).text.strip()
    except:
        info["final_price"] = ""
    try:
        info["wallet_price"] = driver.find_element(By.CSS_SELECTOR, "span.price-block__wallet-price.red-price").text.strip()
    except:
        info["wallet_price"] = ""
    try:
        info["old_price"] = driver.find_element(By.CSS_SELECTOR, "del.price-block__old-price span").text.strip()
    except:
        info["old_price"] = ""

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
    except:
        info["description"] = ""

    # Изображения
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, details.get("images", ""))
        info["detail_images"] = [i.get_attribute("src") for i in imgs]
    except:
        info["detail_images"] = []

    # Характеристики
    try:
        raw = driver.find_element(By.CSS_SELECTOR, details.get("characteristics", "")).text
        info["characteristics"] = raw
        parsed = parse_characteristics(raw)
        info["characteristics_parsed"] = normalize_characteristics(parsed)
    except:
        info["characteristics"] = ""
        info["characteristics_parsed"] = {}

    # Wildberries‑popup с дополнительными параметрами
    if marketplace.lower() == "wb":
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
            except:
                info["parameters"] = {}
            # Доп. описание
            try:
                ext = popup.find_element(By.CSS_SELECTOR, "section.product-details__description").text.strip()
                info["description"] = f"{info.get('description','')}\n{ext}"
            except:
                pass
        except Exception as e:
            logger.debug(f"Нет popup‑блока деталей: {e}")

    driver.quit()
    return info


def parse_wb_category_by_pagination(category_url: str, target_count: int) -> list:
    cfg = get_marketplace_config("wb")
    driver = get_webdriver()
    products = []

    try:
        driver.get(category_url)
        time.sleep(5)
        # дождаться lazy‑load первой порции карточек
        try:
            asyncio.run(scroll_page(driver))
        except Exception as e:
            logger.debug(f"Не удалось дождаться подгрузки на первой странице: {e}")

        while len(products) < target_count:
            # скроллим скриптом из конфига
            try:
                driver.execute_script(cfg.get("scroll_script", ""))
            except Exception as e:
                logger.debug(f"scroll_script таймаут: {e}")

            # собираем все карточки на странице
            cards = driver.find_elements(By.CSS_SELECTOR, cfg["product_card_selector"])
            logger.info(f"Обработано страниц, собрано товаров: {len(products)} + новых {len(cards)}")
            for card in cards:
                if len(products) >= target_count:
                    break

                try:
                    title = card.find_element(By.CSS_SELECTOR, cfg["title_selector"]).text
                except:
                    title = "Без названия"
                try:
                    url = card.find_element(By.CSS_SELECTOR, cfg["link_selector"]).get_attribute("href")
                except:
                    url = ""
                try:
                    price_txt = card.find_element(By.CSS_SELECTOR, cfg["price_selector"]).text
                    price_clean = float(re.sub(r"[^\d.]", "", price_txt) or 0)
                except:
                    price_txt, price_clean = "", 0.0

                products.append({
                    "title": title,
                    "price": price_txt,
                    "price_clean": price_clean,
                    "url": url,
                })

            # Пагинация: кликаем «Следующая страница»
            try:
                nxt = driver.find_element(By.CSS_SELECTOR, cfg.get("pagination_next_selector", "a.j-next-page"))
                nxt.click()
                time.sleep(5)
                # подождать подгрузку новых карточек
                try:
                    asyncio.run(scroll_page(driver))
                except Exception as e:
                    logger.debug(f"Не удалось дождаться подгрузки после клика «Следующая»: {e}")
            except Exception:
                break

    finally:
        driver.quit()


    detailed = []
    for p in products:
        if p["url"]:
            info = asyncio.run(asyncio.to_thread(get_full_product_info, p["url"], "wb"))
            p.update(info)
        detailed.append(p)

    return detailed
