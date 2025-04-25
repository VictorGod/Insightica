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
from bs4 import BeautifulSoup

from ..config import get_selenium_config, get_marketplace_config, PROXIES

logger = logging.getLogger(__name__)

def get_webdriver():
    opts = Options()
    # Headless и основные флаги
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-extensions")

    # Указываем путь к системному Chromium
    opts.binary_location = "/usr/bin/chromium"

    # Проксирование через локальный SOCKS5
    proxy = random.choice(PROXIES)
    opts.add_argument(f"--proxy-server={proxy}")

    # Используем системный chromedriver
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    return driver

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
