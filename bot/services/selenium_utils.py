import asyncio
import json
import logging
import os
import time
import random
import signal
import subprocess
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
def kill_chrome_processes():
    """Принудительно убивает все процессы Chrome"""
    try:
        subprocess.run(['pkill', '-f', 'chrome'], stderr=subprocess.DEVNULL, timeout=5)
        subprocess.run(['pkill', '-f', 'google-chrome'], stderr=subprocess.DEVNULL, timeout=5)
        subprocess.run(['pkill', '-f', 'chromedriver'], stderr=subprocess.DEVNULL, timeout=5)
        time.sleep(1)
    except Exception:
        pass

def cleanup_chrome_dirs():
    """Очищает временные директории Chrome"""
    try:
        subprocess.run(['rm', '-rf', '/tmp/chrome-user-data'], stderr=subprocess.DEVNULL, timeout=5)
        subprocess.run(['rm', '-rf', '/tmp/crashes'], stderr=subprocess.DEVNULL, timeout=5)
        subprocess.run(['rm', '-rf', '/tmp/.com.google.Chrome*'], stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass

def get_webdriver():
    """
    Создаёт Chrome WebDriver с флагами для стабильной работы в Docker/серверной среде.
    """
    
    kill_chrome_processes()
    cleanup_chrome_dirs()
    
    # Создаем временные директории заново
    os.makedirs("/tmp/chrome-user-data", exist_ok=True)
    os.makedirs("/tmp/crashes", exist_ok=True)

    cfg = get_selenium_config()
    headless = cfg.get("headless", True)
    user_agents = cfg.get("user_agents", [])
    proxies = cfg.get("proxies", [])
    max_attempts = cfg.get("max_driver_attempts", 3)
    page_timeout = cfg.get("page_load_timeout", 30)

    opts = Options()

    # Указываем путь к Chrome (важно для Docker окружения):
    chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome")
    opts.binary_location = chrome_bin  

    # Современный headless режим
    if headless:
        opts.add_argument("--headless=new")

    # Флаги для серверной контейнерной среды:
    container_args = [
    # === Основные флаги безопасности и изоляции ===
    "--no-sandbox",
    "--disable-dev-shm-usage",  # Убрал дублирование
    "--disable-gpu",
    "--disable-web-security",
    "--disable-features=VizDisplayCompositor",
    "--disable-ipc-flooding-protection",
    
    # === Отключение автоматизации и детектирования ботов ===
    "--disable-blink-features=AutomationControlled",
    "--exclude-switches=enable-automation",
    "--disable-automation",
    "--disable-infobars",
    
    # === Оптимизация производительности и памяти ===
    "--memory-pressure-off", 
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-hang-monitor",
    "--disable-client-side-phishing-detection",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-sync",
    
    # === Отключение ненужных функций ===
    "--disable-extensions",
    "--disable-plugins",
    "--disable-java",
    "--disable-translate",
    "--disable-features=TranslateUI",
    "--disable-default-apps",
    "--disable-component-extensions-with-background-pages",
    "--disable-background-networking",
    
    # === Настройки окна и отображения ===
    "--window-size=1920,1080",
    "--start-maximized",
    "--disable-notifications",
    "--disable-desktop-notifications",
    
    # === Системные настройки ===
    "--no-default-browser-check",
    "--no-first-run",
    "--disable-dev-tools",
    "--disable-crash-reporter",
    "--disable-logging",
    "--silent",
    "--disable-device-discovery-notifications",
    
    # === Управление данными и кэшем ===
    "--user-data-dir=/tmp/chrome-user-data",
    "--crash-dumps-dir=/tmp/crashes", 
    "--disk-cache-dir=/tmp/cache",
    "--disk-cache-size=104857600",  # 100MB кэш
    "--aggressive-cache-discard",
    
    # === Дополнительные флаги стабильности ===
    "--disable-software-rasterizer",
    "--disable-threaded-animation",
    "--disable-threaded-scrolling",
    "--disable-checker-imaging",
    "--disable-new-bookmark-apps",
    "--disable-search-geolocation-disclosure",
    "--disable-background-mode",
    "--disable-add-to-shelf",
    "--disable-gesture-typing",
    
    # === Сетевые оптимизации ===
    "--disable-background-downloads",
    "--disable-domain-reliability",
    "--disable-features=MediaRouter",
    "--disable-print-preview",
    
    # === Производительность процессора ===
    "--max_old_space_size=4096",
    "--process-per-site",

    
    # === Дополнительные флаги для headless режима ===
    "--hide-scrollbars",
    "--mute-audio",
    "--disable-audio-output",
    "--disable-bundled-ppapi-flash",
    "--disable-logging",
    "--disable-plugins-discovery",
    "--disable-preconnect",
    
    # === Флаги для устранения утечек памяти ===
    "--memory-pressure-off",
    "--disable-renderer-accessibility", 
    "--disable-speech-api",
    "--disable-file-system",
    "--disable-shared-workers",
    "--disable-web-sockets"
]

    # Добавляем все аргументы
    for arg in container_args:
        opts.add_argument(arg)

    # Добавляем случайный User-Agent (по желанию)
    if user_agents:
        opts.add_argument(f"user-agent={random.choice(user_agents)}")
    if proxies:
        opts.add_argument(f"--proxy-server={random.choice(proxies)}")

    driver = None
    for attempt in range(1, max_attempts + 1):
        try:
            driver = webdriver.Chrome(
                options=opts,
                service=Service(ChromeDriverManager().install())
            )
            driver.set_page_load_timeout(page_timeout)
            # Проверим работоспособность
            driver.get("data:text/html,<html><body>Test</body></html>")
            _ = driver.title  # Пробуем прочитать
            return driver
        except WebDriverException as e:
            logger.warning(f"Ошибка запуска WebDriver (попытка {attempt}/{max_attempts}): {e}")
            if 'driver' in locals():
                safe_quit_driver(driver)
            kill_chrome_processes()
            time.sleep(2)

    raise RuntimeError("WebDriver не удалось инициализировать после всех попыток.")

def check_driver_alive(driver):
    """Проверяет что драйвер еще живой"""
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False

def safe_quit_driver(driver):
    """Безопасно закрывает драйвер и убивает все процессы"""
    try:
        if driver:
            driver.quit()
    except Exception:
        pass
    
    # КРИТИЧНО: принудительно убиваем все Chrome процессы
    kill_chrome_processes()
    cleanup_chrome_dirs()

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
                # ИСПОЛЬЗУЕМ безопасное закрытие
                safe_quit_driver(drv)
        await asyncio.sleep(3600)