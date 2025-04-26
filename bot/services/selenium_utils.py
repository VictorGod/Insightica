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

from ..config import get_selenium_config, get_marketplace_config

logger = logging.getLogger(__name__)

def get_webdriver():
    cfg = get_selenium_config()
    opts = Options()
    
    if cfg.get("headless"):
        opts.add_argument("--headless")
    
    opts.add_argument(f"user-agent={random.choice(cfg.get('user_agents', []))}")
    
    for arg in (
        "--disable-extensions",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled"
    ):
        opts.add_argument(arg)
    
    if cfg.get("proxies"):
        opts.add_argument(f"--proxy-server={random.choice(cfg['proxies'])}")
    
    # Определение пути к ChromeDriver (для контейнеров)
    chrome_driver_path = os.environ.get("CHROME_DRIVER_PATH")
    
    max_attempts = cfg.get("max_driver_attempts", 3)
    current_attempt = 0
    last_exception = None
    
    while current_attempt < max_attempts:
        try:
            current_attempt += 1
            
            # Создание драйвера
            if chrome_driver_path and os.path.exists(chrome_driver_path):
                driver = webdriver.Chrome(
                    service=Service(executable_path=chrome_driver_path),
                    options=opts
                )
            else:
                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=opts
                )
            
            driver.set_page_load_timeout(cfg.get("page_load_timeout", 30))
            
            # Внутренняя проверка готовности драйвера
            try:
                test_url = cfg.get("test_url", "https://www.example.com")
                driver.get(test_url)
                # Проверка загрузилась ли страница
                _ = driver.title  # Вызовет исключение, если драйвер не готов
                
                # Если мы дошли сюда, значит драйвер работает корректно
                if current_attempt > 1:
                    print(f"WebDriver успешно инициализирован с {current_attempt} попытки")
                
                return driver
                
            except Exception as e:
                # Что-то пошло не так при загрузке тестовой страницы
                print(f"Ошибка при проверке драйвера: {str(e)}")
                try:
                    driver.quit()
                except:
                    pass
                
                last_exception = e
                continue
                
        except Exception as e:
            print(f"Ошибка при создании драйвера (попытка {current_attempt}/{max_attempts}): {str(e)}")
            last_exception = e
            time.sleep(1)  # Небольшая пауза перед следующей попыткой
    
    # Если все попытки не удались, вызываем исключение
    raise RuntimeError(f"Не удалось инициализировать WebDriver после {max_attempts} попыток. Последняя ошибка: {str(last_exception)}")

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
