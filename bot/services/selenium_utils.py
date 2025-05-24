import asyncio
import json
import logging
import os
import time
import random
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup

from ..config import get_selenium_config, get_marketplace_config

logger = logging.getLogger(__name__)

def get_webdriver():
    """
    Создаёт и возвращает настроенный Chrome WebDriver.
    Использует встроенный Selenium Manager вместо ChromeDriverManager.
    """

    os.makedirs("/tmp/chrome-user-data", exist_ok=True)
    os.makedirs("/tmp/crashes", exist_ok=True)

    cfg = get_selenium_config()
    headless = cfg.get("headless", True)
    user_agents = cfg.get("user_agents", [])
    proxies = cfg.get("proxies", [])
    max_attempts = cfg.get("max_driver_attempts", 3)
    page_timeout = cfg.get("page_load_timeout", 30)
    test_url = cfg.get("test_url", "https://www.example.com")

    opts = Options()
    
    # Указываем путь к Chrome в контейнере:
    chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome")
    opts.binary_location = chrome_bin

    # Современный headless-режим:
    if headless:
        opts.add_argument("--headless=new")

    # Критичные флаги для стабильности в контейнерах:
    container_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage", 
        "--disable-gpu",
        "--disable-extensions",
        "--disable-blink-features=AutomationControlled",
        # Дополнительные флаги для предотвращения краша:
        "--single-process",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI,VizDisplayCompositor",
        "--memory-pressure-off",
        "--remote-debugging-port=9222",
        "--disable-ipc-flooding-protection",

        "--user-data-dir=/tmp/chrome-user-data",    # Решает файловую проблему
        "--disable-crash-reporter",                 # Убирает дополнительные процессы
        "--headless=new",                          # Новый stable headless режим
    ]
    
    for arg in container_args:
        opts.add_argument(arg)

    # User-agent и прокси
    if user_agents:
        opts.add_argument(f"user-agent={random.choice(user_agents)}")
    if proxies:
        opts.add_argument(f"--proxy-server={random.choice(proxies)}")

    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            # ГЛАВНОЕ ИЗМЕНЕНИЕ: убираем service, позволяем Selenium Manager управлять
            driver = webdriver.Chrome(options=opts)
            
            driver.set_page_load_timeout(page_timeout)
            driver.get(test_url)
            _ = driver.title
            
            if attempt > 1:
                logger.info(f"WebDriver инициализирован с попытки {attempt}")
            
            return driver

        except WebDriverException as e:
            logger.warning(f"Attempt {attempt}/{max_attempts} failed: {e}")
            last_exception = e
            
            # Очистка при неудаче
            try:
                if 'driver' in locals():
                    driver.quit()
            except Exception:
                pass
            
            time.sleep(2)

    raise RuntimeError(
        f"Не удалось инициализировать WebDriver после {max_attempts} попыток. "
        f"Последняя ошибка: {last_exception}"
    )

def check_driver_alive(driver):
    """Проверяет что драйвер еще живой"""
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def capture_screenshot(driver, name: str) -> str:
    screenshots_dir = get_selenium_config().get("screenshots_dir", "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(screenshots_dir, f"{name}_{ts}.png")
    driver.save_screenshot(path)
    return path

def save_page_html(driver, name: str) -> str:
    base = os.path.join("marketplace_data", "html_dumps")
    os.makedirs(base, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(base, f"{name}_{ts}.html")
    try:
        html = driver.page_source
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        meta = {
            "url": driver.current_url,
            "timestamp": ts,
            "user_agent": driver.execute_script("return navigator.userAgent;"),
            "viewport": driver.get_window_size(),
            "title": driver.title
        }
        with open(path.replace(".html", "_meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return path
    except Exception as e:
        logger.error(e)
        return None

def analyze_page_structure(html_path: str, marketplace: str):
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            txt = f.read()
        soup = BeautifulSoup(txt, "html.parser")
        cfg  = get_marketplace_config(marketplace)
        report = {}
        for name, sel in cfg.items():
            if isinstance(sel, str) and sel.startswith((".", "#", "div", "[")):
                els = soup.select(sel)
                report[name] = {
                    "found": len(els),
                    "sample": str(els[0])[:200] if els else None
                }
        out = html_path.replace(".html", "_analysis.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.getLogger(__name__).error(e)

async def scroll_page(driver, max_scrolls=5):
    last = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        await asyncio.sleep(2)
        cur = driver.execute_script("return document.body.scrollHeight")
        if cur == last:
            break
        last = cur

async def check_selectors_validity():
    while True:
        for m in ("ozon", "wb"):
            cfg = get_marketplace_config(m)
            drv = get_webdriver()
            try:
                drv.get(cfg["test_url"])
                await asyncio.sleep(5)
                html = save_page_html(drv, f"{m}_test")
                if html:
                    analyze_page_structure(html, m)
            finally:
                drv.quit()
        await asyncio.sleep(3600)
