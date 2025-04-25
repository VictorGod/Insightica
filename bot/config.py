import os
from dotenv import load_dotenv
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
import traceback
import inspect
import json
load_dotenv()
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")



def get_selenium_config():
    """Общие настройки Selenium + Chrome."""
    return {
        "headless": True,
        "page_load_timeout": 30,
        "screenshots_dir": "screenshots",
        "debug_screenshots": True,
        "user_agents": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Edge/123.0.0.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ],
        "implicit_wait": 10,
        "explicit_wait": 20,
        "scroll_pause": 3,
        "page_load_pause": 10,
        "max_scroll_attempts": 7,
        "proxies": [],
        "chrome_options": [
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions"
        ]
    }


def get_marketplace_config(marketplace_name=None):
    """Селекторы и настройки для каждого маркетплейса."""
    # полный стек вызова
    stack = "".join(traceback.format_stack())
    logger.info(f"Stack when get_marketplace_config:\n{stack}")

    # информация о непосредственном вызове
    caller = inspect.stack()[1]
    logger.info(f"get_marketplace_config вызван из {caller.filename}:{caller.lineno}")

    configs = {
        "ozon": {
            "base_url": "https://www.ozon.ru",
            "search_url": "https://www.ozon.ru/search/?text={}",
            "product_url": "https://www.ozon.ru/product/{}",
            "product_card_selector": "div.tile-root",
            "link_selector": "a.tile-clickable-element",
            "title_selector": "a.tile-clickable-element",
            "image_selector": "div.j6q_25 img",
            "price_selector": "span.tsHeadline500Medium",
            "rating_selector": "",
            "reviews_selector": "",
            "load_delay": 30,
            "scroll_pause": 3,
            "max_scroll_attempts": 7,
            "scroll_script": """
                function smoothScroll() {
                    return new Promise(resolve => {
                        let lastY = -1, same = 0;
                        const id = setInterval(() => {
                            window.scrollBy(0, 400);
                            if (window.scrollY === lastY) {
                                same += 1;
                                if (same >= 3) {
                                    clearInterval(id);
                                    resolve();
                                }
                            } else {
                                lastY = window.scrollY;
                            }
                        }, 500);
                    });
                }
                await smoothScroll();
            """,
            "product_detail": {
                "title": "div[data-widget='webProductHeading'] h1",
                "price": "div[data-widget='webPrice'] span",
                "description": "div[data-widget='webDescription']",
                "images": "div[data-widget='webGallery'] img",
                "characteristics": "div[data-widget='webCharacteristics']",
                "reviews_container": "div[data-widget='webReviews']"
            },
        },
        "wb": {
            "base_url": "https://www.wildberries.ru",
            "search_url": "https://www.wildberries.ru/catalog/0/search.aspx?search={}",
            "product_url": "https://www.wildberries.ru/catalog/{}/detail.aspx",
            "product_card_selector": "article.product-card",
            "alternative_selectors": [
                "div.product-card-list article.product-card"
            ],
            "title_selector": "a.product-card__link",
            "price_selector": "",
            "link_selector": "a.product-card__link",
            "image_selector": "div.product-card__img-wrap img.j-thumbnail",
            "rating_selector": "",
            "reviews_selector": "",
            "load_delay": 15,
            "scroll_pause": 4,
            "max_scroll_attempts": 10,
            "scroll_script": """
                function smoothScroll() {
                    return new Promise((resolve) => {
                        let lastScrollTop = 0;
                        const scrollInterval = setInterval(() => {
                            window.scrollTo(0, window.scrollY + 200);
                            if (window.scrollY === lastScrollTop) {
                                clearInterval(scrollInterval);
                                setTimeout(resolve, 2000);
                            }
                            lastScrollTop = window.scrollY;
                        }, 800);
                    });
                }
                await smoothScroll();
            """,
            "parsing": {
                "max_items": 100,
                "batch_size": 10,
                "price_regex": r'[\d\s,.]+',
                "skip_unavailable": True,
                "save_raw_html": False,
            },
            "product_detail": {
                "title": "h1.product-page__title",
                "price": "ins.price-block__final-price.wallet",
                "description": "div.product-page__description",
                "images": "div.product-page__gallery img",
                "characteristics": "div.product-params",
                "parameters_selector": "div.product-params",
                "reviews_container": "div.product-page__reviews"
            },
            "pagination_next_selector": "a.pagination-next.j-next-page",
            "pagination_numbers_selector": "a.pagination-item.j-page"
        }
    }

    if marketplace_name:
        key = marketplace_name.lower()
        cfg = configs.get(key, {})
        logger.info(
            f"=== Конфиг для маркетплейса {key!r} ===\n"
            f"{json.dumps(cfg, ensure_ascii=False, indent=2)}"
        )
        return cfg

    logger.info(
        "=== Конфиг всех маркетплейсов ===\n"
        + json.dumps(configs, ensure_ascii=False, indent=2)
    )
    return configs

# -------------------------------------------------------------------
# Настройки сохранения данных
# -------------------------------------------------------------------
DATA_STORAGE = {
    "base_dir": "marketplace_data",
    "subdirs": {
        "images": "images",
        "csv": "csv",
        "reports": "reports",
        "logs": "logs",
        "debug": "debug",
        "raw": "raw_html"
    },
    "file_formats": {
        "csv": {
            "encoding": "utf-8-sig",
            "delimiter": ";",
            "quoting": "minimal"
        },
        "images": {
            "format": "JPEG",
            "quality": 85,
            "max_size": (1200, 1200)
        }
    }
}

BASE_DIR = DATA_STORAGE["base_dir"]
CSV_DIR = os.path.join(BASE_DIR, DATA_STORAGE["subdirs"]["csv"])
REPORTS_DIR = os.path.join(BASE_DIR, DATA_STORAGE["subdirs"]["reports"])
IMAGES_DIR = os.path.join(BASE_DIR, DATA_STORAGE["subdirs"]["images"])
RAW_HTML_DIR = os.path.join(BASE_DIR, DATA_STORAGE["subdirs"]["raw"])


# -------------------------------------------------------------------
# Логирование
# -------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose"
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "marketplace_bot.log",
            "formatter": "verbose"
        }
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO"
    }
}


# -------------------------------------------------------------------
# Настройки аналитики
# -------------------------------------------------------------------
ANALYSIS_CONFIG = {
    "charts": {
        "dpi": 300,
        "figure_size": (15, 10),
        "style": "seaborn",
        "colors": ["#2196F3", "#4CAF50", "#FFC107", "#F44336"]
    },
    "price_analysis": {
        "bins": 30,
        "histogram_alpha": 0.7,
        "scatter_alpha": 0.5
    },
    "time_analysis": {
        "rolling_window": 7,
        "min_periods": 1
    }
}
