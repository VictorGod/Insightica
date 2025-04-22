from aiogram.fsm.state import State, StatesGroup

class MarketplaceForm(StatesGroup):
    """Состояния для работы с маркетплейсами"""
    # Состояния для WildBerries
    waiting_for_wb_category_url = State()
    waiting_for_wb_product_url = State()
    waiting_for_wb_item_count = State() 
    
    # Состояния для Ozon
    waiting_for_ozon_category_url = State()
    waiting_for_ozon_product_url = State()
    waiting_for_ozon_item_count = State()
    
    # Состояния для анализа цен
    waiting_for_csv_choice = State()
    
    # Состояния для мониторинга цен
    waiting_for_monitoring_urls = State()
    waiting_for_monitoring_period = State()
    
    # Общие состояния
    processing = State()
    waiting_for_command = State()

    

class Form(StatesGroup):
    waiting_for_url = State()
    waiting_for_group_url = State()
    waiting_for_tags = State()
    waiting_for_max_videos = State()
    waiting_for_channel_url = State()
    waiting_for_site_choice = State()
    waiting_for_site_selection = State()
