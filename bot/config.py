import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Токен бота
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

def get_selenium_config():
    """Конфигурация для Selenium"""
    return {
        "headless": True,  # Запуск браузера в фоновом режиме
        "page_load_timeout": 30,  # Таймаут загрузки страницы
        "screenshots_dir": "screenshots",  # Директория для скриншотов
        "debug_screenshots": True,  # Включить создание скриншотов для отладки
        # Список User-Agent для ротации
        "user_agents": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Edge/123.0.0.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ],
        # Настройки ожидания
        "implicit_wait": 10,
        "explicit_wait": 20,
        "scroll_pause": 2,
        "page_load_pause": 10,
        "max_scroll_attempts": 5,
        # Список прокси для ротации (если нужно)
        "proxies": [],
        # Дополнительные настройки Chrome
        "chrome_options": [
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions"
        ]
    }

def get_marketplace_config(marketplace_name=None):
    """Конфигурация для маркетплейсов"""
    configs = {
        "ozon": {
            "base_url": "https://www.ozon.ru",
            "search_url": "https://www.ozon.ru/search/?text={}",
            "product_url": "https://www.ozon.ru/product/{}",
            "api_url": "https://www.ozon.ru/api/composer-api.bx/page/json/v2",
            "product_card_selector": ".mj9_25.nj_25.tile-root",
            "link_selector": "a.tile-clickable-element",
            "title_selector": "a.tile-clickable-element",
            "price_selector": "span.c2h5 span, span.p2h5",
            "image_selector": "img.tile-image, img.i3y",
            "rating_selector": "div.tile-rating, span.tile-rating",
            "reviews_selector": "div.tile-reviews, span.tile-reviews, [data-test-id='tile-list-comments']",
            "load_delay": 30,
            "scroll_pause": 3,
            "max_scroll_attempts": 7,
            "scroll_script": """
                function smoothScroll() {
                    return new Promise((resolve) => {
                        let lastScrollTop = 0;
                        const scrollInterval = setInterval(() => {
                            window.scrollTo(0, window.scrollY + 300);
                            if (window.scrollY === lastScrollTop) {
                                clearInterval(scrollInterval);
                                resolve();
                            }
                            lastScrollTop = window.scrollY;
                        }, 500);
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
                "title": "div[data-widget='webProductHeading'] h1",
                "price": "div[data-widget='webPrice'] span",
                "description": "div[data-widget='webDescription']",
                "images": "div[data-widget='webGallery'] img",
                "characteristics": "div[data-widget='webCharacteristics']",
                "reviews_container": "div[data-widget='webReviews']"
            },
            "test_url": "https://www.ozon.ru/category/smartfony-15502/?__rr=1&abt_att=1"
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
            "price_selector": "",  # На страницах категории цена может отсутствовать
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
                # Обновлённый селектор цены для Wildberries:
                "price": "ins.price-block__final-price.wallet",
                "description": "div.product-page__description",
                "images": "div.product-page__gallery img",
                # Если требуется сохранить raw-характеристики – можно оставить, но сейчас будем получать параметры отдельно:
                "characteristics": "div.product-params",
                # Новый ключ для непосредственно получения структуры параметров:
                "parameters_selector": "div.product-params",
                "reviews_container": "div.product-page__reviews"
            },
            "pagination_next_selector": "a.pagination-next.j-next-page",
            "pagination_numbers_selector": "a.pagination-item.j-page"
        }
    }
    if marketplace_name:
        return configs.get(marketplace_name.lower(), {})
    return configs
     
# Настройки сохранения данных
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

# Настройки логирования
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

# Настройки анализа данных
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
