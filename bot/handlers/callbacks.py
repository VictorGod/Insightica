from bot.handlers.commands import dp

# Импорт всех обработчиков
from bot.handlers.category.wb_category import *
from bot.handlers.category.ozon_category import *
from bot.handlers.product.wb_product import *
from bot.handlers.product.ozon_product import *
from bot.handlers.analysis import handle_analyze_prices
from bot.handlers.monitoring import handle_price_monitoring
