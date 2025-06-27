import asyncio
import json
import logging
import os
import time
import random
import subprocess
import shutil
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
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


def log_system_state():
    """Логирует состояние памяти, диска и содержимое /tmp/crashes"""
    # Память
    try:
        meminfo = {}
        with open('/proc/meminfo') as f:
            for line in f:
                key, val = line.split(':', 1)
                meminfo[key] = val.strip()
        logger.error(f"--- /proc/meminfo ---\n{json.dumps(meminfo, indent=2)}")
    except Exception as e:
        logger.error(f"Не удалось прочитать /proc/meminfo: {e}")

    # Диск
    try:
        for path in ['/', '/tmp']:
            total, used, free = shutil.disk_usage(path)
            logger.error(f"Disk {path}: total={total//2**20}MB used={used//2**20}MB free={free//2**20}MB")
    except Exception as e:
        logger.error(f"Не удалось получить данные о диске: {e}")

    # Содержимое /tmp/crashes
    try:
        crashes = os.listdir('/tmp/crashes')
        logger.error(f"Contents of /tmp/crashes: {crashes}")
    except Exception as e:
        logger.error(f"Не удалось прочитать /tmp/crashes: {e}")


def get_webdriver():
    """
    Создаёт Chrome WebDriver с флагами для стабильной работы в Docker/серверной среде.
    При ошибках собирает логи chromedriver, Chrome, и системное состояние для диагностики.
    """
    kill_chrome_processes()
    cleanup_chrome_dirs()

    os.makedirs("/tmp/chrome-user-data", exist_ok=True)
    os.makedirs("/tmp/crashes", exist_ok=True)
    os.makedirs("/tmp/logs", exist_ok=True)

    cfg = get_selenium_config()
    headless = cfg.get("headless", True)
    user_agents = cfg.get("user_agents", [])
    proxies = cfg.get("proxies", [])
    max_attempts = cfg.get("max_driver_attempts", 3)
    page_timeout = cfg.get("page_load_timeout", 30)

    opts = Options()
    opts.binary_location = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome")
    if headless:
        opts.add_argument("--headless=new")

    container_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--user-data-dir=/tmp/chrome-user-data",
        "--crash-dumps-dir=/tmp/crashes",
        "--window-size=1920,1080",
        "--single-process",
        "--no-zygote",
        "--enable-logging",
        "--v=1",
        "--log-path=/tmp/logs/chrome.log",
    ]
    for arg in container_args:
        opts.add_argument(arg)

    if user_agents:
        opts.add_argument(f"user-agent={random.choice(user_agents)}")
    if proxies:
        opts.add_argument(f"--proxy-server={random.choice(proxies)}")

    chromedriver_log = "/tmp/logs/chromedriver.log"
    try:
        os.remove(chromedriver_log)
    except OSError:
        pass

    service = Service(
        ChromeDriverManager().install(),
        log_path=chromedriver_log,
        service_args=["--verbose"]
    )

    driver = None
    for attempt in range(1, max_attempts + 1):
        try:
            driver = webdriver.Chrome(options=opts, service=service)
            driver.set_page_load_timeout(page_timeout)
            driver.get("data:text/html,<html><body>Test</body></html>")
            _ = driver.title
            return driver

        except WebDriverException as e:
            logger.warning(f"Ошибка запуска WebDriver (попытка {attempt}/{max_attempts}): {e}")

            # Хвост chromedriver.log
            if os.path.exists(chromedriver_log):
                with open(chromedriver_log, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
                logger.error("--- Последние 50 строк chromedriver.log ---\n" + "\n".join(lines[-50:]))

            # Хвост chrome.log
            chrome_log = "/tmp/logs/chrome.log"
            if os.path.exists(chrome_log):
                with open(chrome_log, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
                logger.error("--- Последние 50 строк chrome.log ---\n" + "\n".join(lines[-50:]))

            # Логируем состояние системы
            log_system_state()

            if driver:
                safe_quit_driver(driver)
            kill_chrome_processes()
            time.sleep(2)

    raise RuntimeError("WebDriver не удалось инициализировать после всех попыток.")


def check_driver_alive(driver):
    """Проверяет, что драйвер ещё живой"""
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
        cfg = get_marketplace_config(marketplace)
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
        logger.error(e)


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
                safe_quit_driver(drv)
        await asyncio.sleep(3600)
