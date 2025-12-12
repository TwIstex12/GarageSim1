import asyncio 
import random 
import time 
import json 
import os 
import string 
import sys 
import shutil 
import glob
from aiogram import Bot, Dispatcher, types 
from aiogram.utils import executor 
from aiogram.utils.exceptions import Unauthorized
from aiohttp import web
from datetime import datetime, timedelta 
from typing import Dict, Any, List 

# ========== CONFIG & GLOBALS =========== 
TOKEN = "8098891662:AAFqbb0db3MT7d4iTXQZeTCaf_6z9GJDWfA" 
OWNER_ID = 1678023162 
IMAGE_BASE_PATH = 'images/' 
DATA_FILE = 'bot_data.json' 
COOLDOWN = 3 * 60 * 60

bot = Bot(token=TOKEN) 
dp = Dispatcher(bot) 

# Global runtime state 
user_balance: Dict[int, int] = {} 
user_garage: Dict[int, List[Dict[str, Any]]] = {} 
car_owner_map: Dict[str, int] = {} 
user_shop_limits: Dict[int, Dict[str, Any]] = {} 
last_use: Dict[int, float] = {} 
trade_offers: Dict[str, Dict[str, Any]] = {} 
race_challenges: Dict[str, Dict[str, Any]] = {} 
daily_gift: Dict[int, float] = {} 

# Система квестов
user_quests: Dict[int, Dict[str, Any]] = {}
user_achievements: Dict[int, Dict[str, Any]] = {}

# Система промокодов
promocodes: Dict[str, Dict[str, Any]] = {}
used_promocodes: Dict[int, List[str]] = {}

# Система крафта
crafting_recipes: Dict[str, Dict[str, Any]] = {}

# Система аукциона
auctions: Dict[str, Dict[str, Any]] = {}
user_bids: Dict[str, Dict[int, int]] = {}

# Система гонок
active_races: Dict[str, Dict[str, Any]] = {}
race_invitations: Dict[str, Dict[str, Any]] = {}

# ========== НОВЫЕ СИСТЕМЫ ==========

# Система каршеринга
user_carsharing: Dict[int, Dict[str, Any]] = {}
carsharing_income: Dict[int, float] = {}

# Система таксопарка
user_taxipark: Dict[int, Dict[str, Any]] = {}
taxipark_income: Dict[int, float] = {}

# Система барахолки (вторичный рынок)
flea_market: Dict[str, Dict[str, Any]] = {}
flea_pending: Dict[int, str] = {}

# Система скрапа
user_scrap: Dict[int, int] = {}

# Система розыгрышей
active_giveaway: Dict[str, Any] = {}
# giveaway_participants: mapping user_id -> {'joined_at': float, 'note': Optional[str]}
giveaway_participants: Dict[int, Dict[str, Any]] = {}
pending_giveaway_clarify: Dict[int, bool] = {}

# Система подписок
SUBS_CHANNEL_ID = None  # channel username or id for subscription check
user_subscriptions: Dict[int, Dict[str, Any]] = {}

# ========== СИСТЕМА ТЕМАТИЧЕСКИХ ОБНОВЛЕНИЙ ==========

# Текущее активное событие
current_event = None
event_start_date = None
event_end_date = None

# Определение событий по датам
EVENTS = {
    "halloween": {
        "name": "🎃 ХЭЛЛОУИН",
        "start_month": 10,
        "start_day": 25,
        "end_month": 11,
        "end_day": 2,
        "bonus_multiplier": 1.5,
        "special_cars": [
            "Halloween Ghost Rider", "Pumpkin King", "Nightmare Bat", 
            "Zombie Slayer", "Dark Phantom", "Witch's Brew"
        ],
        "theme_color": "🟠",
        "bonus_message": "🎃 Хэллоуинское безумие! Шанс получить редкую машину увеличен!",
        "decorations": {
            "main_emoji": "🎃",
            "shop_emoji": "🦇",
            "car_emoji": "👻",
            "money_emoji": "💀",
            "garage_emoji": "🏚️"
        }
    },
    "new_year": {
        "name": "🎄 НОВЫЙ ГОД",
        "start_month": 12,
        "start_day": 20,
        "end_month": 1,
        "end_day": 10,
        "bonus_multiplier": 2.0,
        "special_cars": [
            "Santa's Sleigh", "Snow Drifter", "Ice Queen", 
            "Frost Bite", "Polar Express", "Gift Wrapper"
        ],
        "theme_color": "🟢",
        "bonus_message": "🎄 Новогоднее чудо! Шанс получить легендарную машину удвоен!",
        "decorations": {
            "main_emoji": "🎄",
            "shop_emoji": "🎁",
            "car_emoji": "🛷",
            "money_emoji": "❄️",
            "garage_emoji": "🏡"
        }
    },
    "summer": {
        "name": "☀️ ЛЕТНЕЕ БЕЗУМИЕ",
        "start_month": 6,
        "start_day": 15,
        "end_month": 8,
        "end_day": 31,
        "bonus_multiplier": 1.3,
        "special_cars": [
            "Summer Cruiser", "Beach Buggy", "Sunset Racer",
            "Tropical Storm", "Ocean Drifter", "Heat Wave"
        ],
        "theme_color": "🟡",
        "bonus_message": "☀️ Летняя жара! Бонус к шансу получения машин!",
        "decorations": {
            "main_emoji": "☀️",
            "shop_emoji": "🏖️",
            "car_emoji": "🌊",
            "money_emoji": "🌴",
            "garage_emoji": "🏝️"
        }
    }
}

# Редкости/категории, доступные только подписчикам
PREMIUM_RARITIES = {"Эксклюзивные", "Легендарные"}

def check_current_event():
    """Проверяет текущее событие по дате"""
    global current_event, event_start_date, event_end_date
    
    now = datetime.now()
    
    for event_id, event_data in EVENTS.items():
        start_date = datetime(now.year, event_data["start_month"], event_data["start_day"])
        end_date = datetime(now.year, event_data["end_month"], event_data["end_day"])
        
        # Корректируем для событий, переходящих через год
        if event_data["end_month"] < event_data["start_month"]:
            end_date = datetime(now.year + 1, event_data["end_month"], event_data["end_day"])
        
        if start_date <= now <= end_date:
            current_event = event_id
            event_start_date = start_date
            event_end_date = end_date
            return
    
    current_event = None
    event_start_date = None
    event_end_date = None

def get_event_bonus():
    """Возвращает бонус текущего события"""
    if current_event:
        return EVENTS[current_event]["bonus_multiplier"]
    return 1.0

def get_event_special_cars():
    """Возвращает специальные машины события"""
    if current_event:
        return EVENTS[current_event]["special_cars"]
    return []

def get_event_message():
    """Возвращает сообщение о текущем событии"""
    if current_event:
        event_data = EVENTS[current_event]
        days_left = (event_end_date - datetime.now()).days
        return f"{event_data['theme_color']} {event_data['name']}\n{event_data['bonus_message']}\n⏰ Осталось: {days_left} дней"
    return None

def get_event_decorations():
    """Возвращает оформление для текущего события"""
    if current_event:
        return EVENTS[current_event]["decorations"]
    return {
        "main_emoji": "🚗",
        "shop_emoji": "🛒",
        "car_emoji": "🏎️",
        "money_emoji": "💰",
        "garage_emoji": "🅿️"
    }

# ========== КАТАЛОГ МАШИН С УЧЕТОМ СОБЫТИЙ ==========

def get_cars_with_events():
    """Возвращает каталог машин с учетом текущего события"""
    cars_catalog = { 
        'Обычные': [
            'Toyota Supra', 'Nissan Skyline', "Opel Astra", "Honda Civic", 
            "Toyota Corolla", "Ford Focus", "Volkswagen Golf", "Mazda MX-5",
            "Hyundai Elantra", "Kia Rio", "Chevrolet Cruze", "Renault Logan",
            "Skoda Octavia", "Peugeot 308", "Fiat Punto", "Volvo S60",
            "Mitsubishi Lancer", "Subaru Impreza", "BMW 3 Series", "Audi A4",
            "Mercedes A-Class", "Volkswagen Passat", "Toyota Camry", "Honda Accord",
            "Ford Mondeo", "Nissan Altima", "Hyundai Sonata", "Kia Optima",
            "Chevrolet Malibu", "Renault Megane", "Opel Insignia", "Seat Leon"
        ], 
        'Редкие': [
            'Porsche 911', 'Ferrari F40', 'Ford Mustang GT', 'Subaru WRX STI', 
            'BMW M3', 'Nissan GT-R R34', "Mercedes C63 AMG", "Audi TT",
            "Lexus IS", "Infiniti Q50", "Jaguar XE", "Cadillac CTS",
            "Alfa Romeo Giulia", "Maserati Ghibli", "Tesla Model 3", "Porsche Cayman",
            "BMW M5", "Mercedes E63", "Audi RS5", "Chevrolet Camaro",
            "Dodge Challenger", "Nissan 370Z", "Toyota GR86", "Subaru BRZ",
            "Audi S4", "BMW M4", "Mercedes CLA45", "Volkswagen Golf R",
            "Honda NSX", "Acura Integra", "Mazda RX-7", "Toyota MR2"
        ], 
        'Эпические': [
            'Lamborghini Aventador', 'Porsche 911 Turbo', 'Lamborghini Gallardo',
            "Ferrari 488", "McLaren 720S", "Aston Martin Vantage", "Maserati GranTurismo",
            "Audi R8", "Mercedes AMG GT", "Nissan GT-R Nismo", "Porsche 911 GT3",
            "Ferrari Roma", "Lamborghini Huracan", "McLaren 570S", "Aston Martin DB11",
            "Ferrari F8 Tributo", "McLaren 650S", "Lamborghini Murcielago", "Porsche 918 Spyder",
            "Ferrari 812 Superfast", "Aston Martin DBS", "Mercedes SLS AMG", "Audi R8 V10",
            "Nissan GT-R50", "Lexus LFA", "Acura NSX", "Chevrolet Corvette Z06",
            "Dodge Viper", "Jaguar F-Type", "BMW i8", "Tesla Model S Plaid"
        ], 
        'Легендарные': [
            'Bugatti Veyron', 'Bugatti Chiron', "Koenigsegg Agera", "Pagani Huayra",
            "Ferrari LaFerrari", "McLaren P1", "Porsche 918 Spyder", "Koenigsegg Jesko",
            "Pagani Zonda", "Bugatti Divo", "Lamborghini Sian", "Ferrari SF90 Stradale",
            "Koenigsegg Regera", "Bugatti Bolide", "McLaren Speedtail", "Aston Martin Valkyrie",
            "Mercedes Project One", "Ferrari Daytona SP3", "Lamborghini Countach", "Pagani Utopia",
            "Bugatti Centodieci", "Koenigsegg Gemera", "Rimac Nevera", "Lotus Evija",
            "Ferrari Monza", "McLaren Sabre", "Bugatti Mistral", "Koenigsegg CCXR"
        ], 
        'Эксклюзивные': [
            "Rolls Royce Phantom", "Bentley Continental GT", "Mercedes Maybach",
            "Aston Martin Valkyrie", "Koenigsegg Gemera", "Rimac Nevera",
            "Ferrari 250 GTO", "Mercedes 300SL", "Jaguar E-Type", "Porsche 550 Spyder",
            "Shelby Cobra", "Ferrari Testarossa", "Lamborghini Miura", "Ford GT40",
            "McLaren F1", "Ferrari Enzo", "Porsche Carrera GT", "Saleen S7"
        ],
        'Скраповые': [
            "Scrap Warrior", "Junk King", "Rusty Racer", "Recycled Rocket",
            "Salvage Speedster", "Trash Titan", "Waste Whip", "Garbage Glider"
        ]
    }
    
    # Добавляем специальные машины события в магазин
    check_current_event()
    if current_event:
        special_cars = get_event_special_cars()
        event_name = EVENTS[current_event]["name"]
        cars_catalog[event_name] = special_cars
    
    return cars_catalog

# Динамический каталог машин
cars = get_cars_with_events()

# Полное сопоставление машин и фотографий
CAR_FILE_MAPPING = {
    # Обычные
    "Toyota Supra": "supra.png",
    "Nissan Skyline": "skyline.png", 
    "Opel Astra": "Astra.png", 
    "Honda Civic": "Civik.png", 
    "Toyota Corolla": "Corolla.png", 
    "Ford Focus": "Focus.png", 
    "Volkswagen Golf": "golf.png",
    "Mazda MX-5": "default.png",
    "Hyundai Elantra": "default.png",
    "Kia Rio": "default.png",
    "Chevrolet Cruze": "default.png",
    "Renault Logan": "default.png",
    "Skoda Octavia": "default.png",
    "Peugeot 308": "default.png",
    "Fiat Punto": "default.png",
    "Volvo S60": "default.png",
    "Mitsubishi Lancer": "default.png",
    "Subaru Impreza": "default.png",
    "BMW 3 Series": "default.png",
    "Audi A4": "default.png",
    "Mercedes A-Class": "default.png",
    "Volkswagen Passat": "default.png",
    "Toyota Camry": "default.png",
    "Honda Accord": "default.png",
    "Ford Mondeo": "default.png",
    "Nissan Altima": "default.png",
    "Hyundai Sonata": "default.png",
    "Kia Optima": "default.png",
    "Chevrolet Malibu": "default.png",
    "Renault Megane": "default.png",
    "Opel Insignia": "default.png",
    "Seat Leon": "default.png",
    
    # Редкие
    "Porsche 911": "porsche_911.png",
    "Ferrari F40": "ferrari_f40.png",
    "Ford Mustang GT": "Mustang.png", 
    "Subaru WRX STI": "Subaru_WRX_STI.png", 
    "BMW M3": "M3.png", 
    "Nissan GT-R R34": "Nissan.png",
    "Mercedes C63 AMG": "AMG.png",
    "Audi TT": "default.png",
    "Lexus IS": "default.png",
    "Infiniti Q50": "default.png",
    "Jaguar XE": "default.png",
    "Cadillac CTS": "default.png",
    "Alfa Romeo Giulia": "default.png",
    "Maserati Ghibli": "default.png",
    "Tesla Model 3": "default.png",
    "Porsche Cayman": "default.png",
    "BMW M5": "default.png",
    "Mercedes E63": "default.png",
    "Audi RS5": "default.png",
    "Chevrolet Camaro": "default.png",
    "Dodge Challenger": "default.png",
    "Nissan 370Z": "default.png",
    "Toyota GR86": "default.png",
    "Subaru BRZ": "default.png",
    "Audi S4": "default.png",
    "BMW M4": "default.png",
    "Mercedes CLA45": "default.png",
    "Volkswagen Golf R": "default.png",
    "Honda NSX": "default.png",
    "Acura Integra": "default.png",
    "Mazda RX-7": "default.png",
    "Toyota MR2": "default.png",
    
    # Эпические
    "Lamborghini Aventador": "aventador.png",
    "Porsche 911 Turbo": "Porshe.png",
    "Lamborghini Gallardo": "Lamborghini.png",
    "Ferrari 488": "default.png",
    "McLaren 720S": "default.png",
    "Aston Martin Vantage": "default.png",
    "Maserati GranTurismo": "default.png",
    "Audi R8": "default.png",
    "Mercedes AMG GT": "default.png",
    "Nissan GT-R Nismo": "default.png",
    "Porsche 911 GT3": "default.png",
    "Ferrari Roma": "default.png",
    "Lamborghini Huracan": "default.png",
    "McLaren 570S": "default.png",
    "Aston Martin DB11": "default.png",
    "Ferrari F8 Tributo": "default.png",
    "McLaren 650S": "default.png",
    "Lamborghini Murcielago": "default.png",
    "Porsche 918 Spyder": "default.png",
    "Ferrari 812 Superfast": "default.png",
    "Aston Martin DBS": "default.png",
    "Mercedes SLS AMG": "default.png",
    "Audi R8 V10": "default.png",
    "Nissan GT-R50": "default.png",
    "Lexus LFA": "default.png",
    "Acura NSX": "default.png",
    "Chevrolet Corvette Z06": "default.png",
    "Dodge Viper": "default.png",
    "Jaguar F-Type": "default.png",
    "BMW i8": "default.png",
    "Tesla Model S Plaid": "default.png",
    
    # Легендарные
    "Bugatti Veyron": "veyron.png",
    "Bugatti Chiron": "Chiron.png",
    "Koenigsegg Agera": "default.png",
    "Pagani Huayra": "default.png",
    "Ferrari LaFerrari": "default.png",
    "McLaren P1": "default.png",
    "Porsche 918 Spyder": "default.png",
    "Koenigsegg Jesko": "default.png",
    "Pagani Zonda": "default.png",
    "Bugatti Divo": "default.png",
    "Lamborghini Sian": "default.png",
    "Ferrari SF90 Stradale": "default.png",
    "Koenigsegg Regera": "default.png",
    "Bugatti Bolide": "default.png",
    "McLaren Speedtail": "default.png",
    "Aston Martin Valkyrie": "default.png",
    "Mercedes Project One": "default.png",
    "Ferrari Daytona SP3": "default.png",
    "Lamborghini Countach": "default.png",
    "Pagani Utopia": "default.png",
    "Bugatti Centodieci": "default.png",
    "Koenigsegg Gemera": "default.png",
    "Rimac Nevera": "default.png",
    "Lotus Evija": "default.png",
    "Ferrari Monza": "default.png",
    "McLaren Sabre": "default.png",
    "Bugatti Mistral": "default.png",
    "Koenigsegg CCXR": "default.png",
    
    # Эксклюзивные
    "Rolls Royce Phantom": "default.png",
    "Bentley Continental GT": "default.png",
    "Mercedes Maybach": "default.png",
    "Aston Martin Valkyrie": "default.png",
    "Koenigsegg Gemera": "default.png",
    "Rimac Nevera": "default.png",
    "Ferrari 250 GTO": "default.png",
    "Mercedes 300SL": "default.png",
    "Jaguar E-Type": "default.png",
    "Porsche 550 Spyder": "default.png",
    "Shelby Cobra": "default.png",
    "Ferrari Testarossa": "default.png",
    "Lamborghini Miura": "default.png",
    "Ford GT40": "default.png",
    "McLaren F1": "default.png",
    "Ferrari Enzo": "default.png",
    "Porsche Carrera GT": "default.png",
    "Saleen S7": "default.png",
    
    # Хэллоуинские машины
    "Halloween Ghost Rider": "default.png",
    "Pumpkin King": "default.png",
    "Nightmare Bat": "default.png",
    "Zombie Slayer": "default.png",
    "Dark Phantom": "default.png",
    "Witch's Brew": "default.png",
    
    # Новогодние машины
    "Santa's Sleigh": "default.png",
    "Snow Drifter": "default.png",
    "Ice Queen": "default.png",
    "Frost Bite": "default.png",
    "Polar Express": "default.png",
    "Gift Wrapper": "default.png",
    
    # Летние машины
    "Summer Cruiser": "default.png",
    "Beach Buggy": "default.png",
    "Sunset Racer": "default.png",
    "Tropical Storm": "default.png",
    "Ocean Drifter": "default.png",
    "Heat Wave": "default.png",
    
    # Скраповые машины
    "Scrap Warrior": "default.png",
    "Junk King": "default.png",
    "Rusty Racer": "default.png",
    "Recycled Rocket": "default.png",
    "Salvage Speedster": "default.png",
    "Trash Titan": "default.png",
    "Waste Whip": "default.png",
    "Garbage Glider": "default.png",
    
    # Запасное изображение
    "Default Model": "default.png"
}

CAR_WEIGHTS = {'Обычные': 50, 'Редкие': 30, 'Эпические': 15, 'Легендарные': 4, 'Эксклюзивные': 0, 'Скраповые': 0}
RARITY_MAP = {'Обычные': 'Обычные', 'Редкие': 'Редкие', 'Эпические': 'Эпические', 'Легендарные': 'Легендарные', 'Эксклюзивные': 'Эксклюзивные', 'Скраповые': 'Скраповые'} 
RARITY_VALUES = {'Обычные': (10000, 30000), 'Редкие': (30000, 70000), 'Эпические': (70000, 150000), 'Легендарные': (150000, 500000), 'Эксклюзивные': (500000, 2000000), 'Скраповые': (50000, 100000)} 
SHOP_PRICE_RANGES = {'Обычные': (10000,30000), 'Редкие': (30000,70000), 'Эпические': (70000,150000), 'Легендарные': (150000,500000)} 

# Система квестов
DAILY_QUESTS = {
    'collect_cars': {
        'name': '🚗 Коллекционер',
        'description': 'Получи 3 машины за сегодня',
        'target': 3,
        'reward': 10000,
        'type': 'daily'
    },
    'win_races': {
        'name': '🏁 Гонщик',
        'description': 'Выиграй 2 гонки',
        'target': 2,
        'reward': 15000,
        'type': 'daily'
    },
    'sell_cars': {
        'name': '💰 Торговец',
        'description': 'Продай 5 машин',
        'target': 5,
        'reward': 8000,
        'type': 'daily'
    },
    'tune_car': {
        'name': '🔧 Тюнинг',
        'description': 'Улучши любую машину',
        'target': 1,
        'reward': 5000,
        'type': 'daily'
    },
    'daily_balance': {
        'name': '💸 Заработок',
        'description': 'Заработай 50,000$ за день',
        'target': 50000,
        'reward': 20000,
        'type': 'daily'
    },
    'craft_car': {
        'name': '🔨 Крафтер',
        'description': 'Создай 1 машину через крафт',
        'target': 1,
        'reward': 12000,
        'type': 'daily'
    },
    'win_auction': {
        'name': '🏆 Аукционер',
        'description': 'Выиграй 1 аукцион',
        'target': 1,
        'reward': 20000,
        'type': 'daily'
    }
}

ACHIEVEMENTS = {
    'first_car': {
        'name': '🎯 Первая машина',
        'description': 'Получи свою первую машину',
        'target': 1,
        'reward': 5000,
        'hidden': False
    },
    'garage_king': {
        'name': '🏆 Король гаража',
        'description': 'Собери 10 машин в гараже',
        'target': 10,
        'reward': 25000,
        'hidden': False
    },
    'race_champion': {
        'name': '🥇 Чемпион гонок',
        'description': 'Выиграй 10 гонок',
        'target': 10,
        'reward': 30000,
        'hidden': False
    },
    'millionaire': {
        'name': '💸 Миллионер',
        'description': 'Накопи 1,000,000$',
        'target': 1000000,
        'reward': 50000,
        'hidden': False
    },
    'car_collector': {
        'name': '📚 Коллекционер',
        'description': 'Собери 25 машин',
        'target': 25,
        'reward': 75000,
        'hidden': False
    },
    'legend_owner': {
        'name': '🌟 Владелец легенд',
        'description': 'Получи 5 легендарных машин',
        'target': 5,
        'reward': 100000,
        'hidden': False
    },
    'master_crafter': {
        'name': '🔨 Мастер крафта',
        'description': 'Создай 10 машин через крафт',
        'target': 10,
        'reward': 40000,
        'hidden': False
    },
    'auction_king': {
        'name': '👑 Король аукционов',
        'description': 'Выиграй 5 аукционов',
        'target': 5,
        'reward': 50000,
        'hidden': False
    }
}

# Система крафта
def init_crafting_system():
    """Инициализация системы крафта"""
    crafting_recipes.clear()
    
    # Рецепты для создания редких машин
    crafting_recipes['rare_from_common'] = {
        'name': 'Создание Редкой машины',
        'description': 'Объедините 2 обычные машины для создания редкой',
        'input_rarity': 'Обычные',
        'input_count': 2,
        'output_rarity': 'Редкие',
        'success_chance': 85,
        'cost': 5000
    }
    
    crafting_recipes['epic_from_rare'] = {
        'name': 'Создание Эпической машины',
        'description': 'Объедините 2 редкие машины для создания эпической',
        'input_rarity': 'Редкие',
        'input_count': 2,
        'output_rarity': 'Эпические',
        'success_chance': 70,
        'cost': 15000
    }
    
    crafting_recipes['legendary_from_epic'] = {
        'name': 'Создание Легендарной машины',
        'description': 'Объедините 2 эпические машины для создания легендарной',
        'input_rarity': 'Эпические',
        'input_count': 2,
        'output_rarity': 'Легендарные',
        'success_chance': 50,
        'cost': 30000,
        'premium': True
    }
    
    crafting_recipes['legendary_from_rare'] = {
        'name': 'Прямое создание Легендарной',
        'description': 'Объедините 3 редкие машины для создания легендарной',
        'input_rarity': 'Редкие',
        'input_count': 3,
        'output_rarity': 'Легендарные',
        'success_chance': 35,
        'cost': 25000,
        'premium': True
    }
    
    crafting_recipes['special_epic'] = {
        'name': 'Специальная Эпическая',
        'description': 'Объедините 1 редкую и 2 обычные для эпической',
        'input_rarity': ['Редкие', 'Обычные'],
        'input_count': [1, 2],
        'output_rarity': 'Эпические',
        'success_chance': 60,
        'cost': 10000,
        'premium': True
    }
    
    # Новые рецепты для скраповых машин
    crafting_recipes['scrap_from_common'] = {
        'name': 'Скрап из Обычной',
        'description': 'Разберите обычную машину для получения скрапа',
        'input_rarity': 'Обычные',
        'input_count': 1,
        'output_rarity': 'Скрап',
        'success_chance': 100,
        'cost': 1000
    }
    
    crafting_recipes['scrap_car'] = {
        'name': 'Скраповая машина',
        'description': 'Создайте скраповую машину из 5 единиц скрапа',
        'input_rarity': 'Скрап',
        'input_count': 5,
        'output_rarity': 'Скраповые',
        'success_chance': 80,
        'cost': 5000
    }

def create_backup(): 
    try: 
        if os.path.exists(DATA_FILE): 
            os.makedirs('backups', exist_ok=True) 
            ts = datetime.now().strftime('%Y%m%d_%H%M%S') 
            shutil.copy2(DATA_FILE, os.path.join('backups', f'bot_data_{ts}.bak')) 
    except Exception: 
        pass 

def save_data(): 
    try: 
        create_backup() 
        shop_limits_serial = {} 
        for k, v in user_shop_limits.items(): 
            lr = v.get('last_reset') 
            shop_limits_serial[str(k)] = {'count': v.get('count', 0), 'last_reset': lr.isoformat() if isinstance(lr, datetime) else str(lr)} 

        quests_serial = {}
        for k, v in user_quests.items():
            quests_serial[str(k)] = v
            
        achievements_serial = {}
        for k, v in user_achievements.items():
            achievements_serial[str(k)] = v

        promocodes_serial = {}
        for k, v in promocodes.items():
            promocodes_serial[k] = v
            
        used_promocodes_serial = {}
        for k, v in used_promocodes.items():
            used_promocodes_serial[str(k)] = v

        auctions_serial = {}
        for k, v in auctions.items():
            auctions_serial[k] = v
            
        user_bids_serial = {}
        for k, v in user_bids.items():
            user_bids_serial[k] = v

        # Новые системы
        carsharing_serial = {}
        for k, v in user_carsharing.items():
            carsharing_serial[str(k)] = v
            
        taxipark_serial = {}
        for k, v in user_taxipark.items():
            taxipark_serial[str(k)] = v
            
        flea_market_serial = {}
        for k, v in flea_market.items():
            flea_market_serial[k] = v
            
        scrap_serial = {}
        for k, v in user_scrap.items():
            scrap_serial[str(k)] = v

        payload = { 
            'user_balance': {str(k): v for k, v in user_balance.items()}, 
            'user_garage': {str(k): v for k, v in user_garage.items()}, 
            'car_owner_map': car_owner_map, 
            'user_shop_limits': shop_limits_serial, 
            'last_use': {str(k): v for k, v in last_use.items()}, 
            'daily_gift': {str(k): v for k, v in daily_gift.items()},
            'user_quests': quests_serial,
            'user_achievements': achievements_serial,
            'promocodes': promocodes_serial,
            'used_promocodes': used_promocodes_serial,
            'auctions': auctions_serial,
            'user_bids': user_bids_serial,
            # Новые системы
            'user_carsharing': carsharing_serial,
            'user_taxipark': taxipark_serial,
            'flea_market': flea_market_serial,
            'user_scrap': scrap_serial
            ,
            # Giveaway
            'active_giveaway': active_giveaway,
            'giveaway_participants': {str(k): v for k, v in giveaway_participants.items()}
            ,
            # Subscriptions
            'subs_channel_id': SUBS_CHANNEL_ID,
            'user_subscriptions': {str(k): v for k, v in user_subscriptions.items()}
        } 
        with open(DATA_FILE, 'w', encoding='utf-8') as f: 
            json.dump(payload, f, ensure_ascii=False, indent=2) 
    except Exception as e: 
        print('save_data error', e) 

def load_data():
    global SUBS_CHANNEL_ID
    try:
        if not os.path.exists(DATA_FILE): 
            return 
        with open(DATA_FILE, 'r', encoding='utf-8') as f: 
            payload = json.load(f) 

        user_balance.clear() 
        for k, v in payload.get('user_balance', {}).items(): 
            try: 
                user_balance[int(k)] = int(v) 
            except Exception: 
                user_balance[int(k)] = v 

        user_garage.clear() 
        for k, v in payload.get('user_garage', {}).items(): 
            try: 
                user_garage[int(k)] = v 
            except Exception: 
                user_garage[k] = v 

        car_owner_map.clear()
        car_owner_map.update(payload.get('car_owner_map', {})) 

        user_shop_limits.clear() 
        for k, v in payload.get('user_shop_limits', {}).items(): 
            try: 
                lr = v.get('last_reset') 
                user_shop_limits[int(k)] = {'count': v.get('count', 0), 'last_reset': datetime.fromisoformat(lr)} 
            except Exception: 
                user_shop_limits[int(k)] = {'count': v.get('count', 0), 'last_reset': datetime.now()} 

        last_use.clear() 
        for k, v in payload.get('last_use', {}).items(): 
            try: 
                last_use[int(k)] = float(v) 
            except Exception: 
                last_use[int(k)] = v 

        daily_gift.clear() 
        for k, v in payload.get('daily_gift', {}).items(): 
            try: 
                daily_gift[int(k)] = float(v) 
            except Exception: 
                daily_gift[int(k)] = v
                
        user_quests.clear()
        for k, v in payload.get('user_quests', {}).items():
            user_quests[int(k)] = v
            
        user_achievements.clear()
        for k, v in payload.get('user_achievements', {}).items():
            user_achievements[int(k)] = v
            
        promocodes.clear()
        promocodes.update(payload.get('promocodes', {}))
        
        used_promocodes.clear()
        for k, v in payload.get('used_promocodes', {}).items():
            used_promocodes[int(k)] = v
            
        auctions.clear()
        auctions.update(payload.get('auctions', {}))
        
        user_bids.clear()
        user_bids.update(payload.get('user_bids', {}))

        # Новые системы
        user_carsharing.clear()
        for k, v in payload.get('user_carsharing', {}).items():
            user_carsharing[int(k)] = v
            
        user_taxipark.clear()
        for k, v in payload.get('user_taxipark', {}).items():
            user_taxipark[int(k)] = v
            
        flea_market.clear()
        flea_market.update(payload.get('flea_market', {}))
        
        user_scrap.clear()
        for k, v in payload.get('user_scrap', {}).items():
            user_scrap[int(k)] = v

        # Giveaway state
        active_giveaway.clear()
        active_giveaway.update(payload.get('active_giveaway', {}))

        giveaway_participants.clear()
        for k, v in payload.get('giveaway_participants', {}).items():
            try:
                giveaway_participants[int(k)] = v
            except Exception:
                giveaway_participants[k] = v

        # Subscriptions
        try:
            SUBS_CHANNEL_ID = payload.get('subs_channel_id')
        except Exception:
            SUBS_CHANNEL_ID = None

        user_subscriptions.clear()
        for k, v in payload.get('user_subscriptions', {}).items():
            try:
                user_subscriptions[int(k)] = v
            except Exception:
                user_subscriptions[k] = v

    except Exception as e: 
        print('load_data error', e) 

# ========== СИСТЕМА ВОССТАНОВЛЕНИЯ ИЗ BACKUP ==========

def find_latest_backup():
    """Находит самый новый backup файл"""
    backup_files = glob.glob('backups/bot_data_*.bak')
    if not backup_files:
        return None
    backup_files.sort(key=os.path.getmtime, reverse=True)
    return backup_files[0]

def find_best_backup_by_content():
    """Находит САМЫЙ ЛУЧШИЙ backup созданный СЕГОДНЯ"""
    backup_files = glob.glob('backups/bot_data_*.bak')
    if not backup_files:
        return None
    
    today = datetime.now().date()
    todays_backups = []
    
    print("🔍 Поиск backup файлов созданных СЕГОДНЯ...")
    
    # Собираем все backup'ы созданные сегодня
    for backup_file in backup_files:
        try:
            file_time = os.path.getmtime(backup_file)
            file_date = datetime.fromtimestamp(file_time).date()
            
            if file_date == today:
                todays_backups.append(backup_file)
                file_time_str = datetime.fromtimestamp(file_time).strftime('%H:%M:%S')
                print(f"   ✅ Найден сегодняшний backup: {os.path.basename(backup_file)} ({file_time_str})")
                
        except Exception as e:
            print(f"   ❌ Ошибка чтения {backup_file}: {e}")
            continue
    
    if not todays_backups:
        print("❌ Не найдено backup файлов за сегодня")
        return None
    
    print(f"📅 Найдено backup за сегодня: {len(todays_backups)} шт.")
    
    # Теперь ищем САМЫЙ ЛУЧШИЙ среди сегодняшних
    best_backup = None
    best_score = -1
    best_balance = 0
    best_cars = 0
    best_time = None
    
    for backup_file in todays_backups:
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Получаем статистику владельца
            owner_balance = int(data.get('user_balance', {}).get(str(OWNER_ID), 0))
            owner_cars = len(data.get('user_garage', {}).get(str(OWNER_ID), []))
            file_time = os.path.getmtime(backup_file)
            file_time_str = datetime.fromtimestamp(file_time).strftime('%H:%M:%S')
            
            # УНИВЕРСАЛЬНАЯ ФОРМУЛА: учитываем и деньги, и машины
            # Даем равный вес деньгам и машинам
            money_normalized = owner_balance / 100000  # 100к$ = 1 балл
            cars_normalized = owner_cars / 10          # 10 машин = 1 балл
            total_score = money_normalized + cars_normalized
            
            print(f"   📊 {os.path.basename(backup_file)} ({file_time_str}):")
            print(f"      💰 Баланс: {format_money(owner_balance)}")
            print(f"      🚗 Машины: {owner_cars}")
            print(f"      📊 Рейтинг: {total_score:.2f} (деньги: {money_normalized:.2f} + машины: {cars_normalized:.2f})")
            
            # Выбираем backup с НАИВЫСШИМ рейтингом
            if total_score > best_score:
                best_score = total_score
                best_backup = backup_file
                best_balance = owner_balance
                best_cars = owner_cars
                best_time = file_time_str
                print(f"      🏆 НОВЫЙ ЛУЧШИЙ BACKUP!")
            elif total_score == best_score:
                # Если рейтинги равны, выбираем более новый
                current_file_time = os.path.getmtime(backup_file)
                best_file_time = os.path.getmtime(best_backup) if best_backup else 0
                if current_file_time > best_file_time:
                    best_backup = backup_file
                    best_balance = owner_balance
                    best_cars = owner_cars
                    best_time = file_time_str
                    print(f"      🏆 ОБНОВЛЕН (более новый при равном рейтинге)!")
                
        except Exception as e:
            print(f"   ❌ Ошибка чтения {backup_file}: {e}")
            continue
    
    if best_backup:
        print(f"🏆 Выбран САМЫЙ ЛУЧШИЙ backup за СЕГОДНЯ: {os.path.basename(best_backup)}")
        print(f"   🕐 Время создания: {best_time}")
        print(f"   💰 Баланс владельца: {format_money(best_balance)}")
        print(f"   🚗 Машин у владельца: {best_cars}")
        print(f"   📊 Итоговый рейтинг: {best_score:.2f} баллов")
        
        return best_backup
    
    print("❌ Не удалось выбрать лучший backup из сегодняшних")
    return None

async def force_restore_if_needed():
    """Принудительное восстановление из САМОГО ЛУЧШЕГО сегодняшнего backup"""
    try:
        backup_file = find_best_backup_by_content()
        if not backup_file:
            print("✅ Не найдено подходящих backup файлов за сегодня")
            return
        
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        # Получаем текущие данные
        main_balance = {}
        main_garage = {}
        
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                main_data = json.load(f)
            main_balance = main_data.get('user_balance', {})
            main_garage = main_data.get('user_garage', {})
        
        # Сравниваем данные владельца
        backup_owner_balance = int(backup_data.get('user_balance', {}).get(str(OWNER_ID), 0))
        backup_owner_cars = len(backup_data.get('user_garage', {}).get(str(OWNER_ID), []))
        main_owner_balance = int(main_balance.get(str(OWNER_ID), 0))
        main_owner_cars = len(main_garage.get(str(OWNER_ID), []))
        
        print(f"📊 Сравнение с текущими данными:")
        print(f"   Текущие: {format_money(main_owner_balance)} | {main_owner_cars} машин")
        print(f"   Лучший сегодняшний backup: {format_money(backup_owner_balance)} | {backup_owner_cars} машин")
        
        # Считаем рейтинги по той же формуле
        backup_money_score = backup_owner_balance / 100000
        backup_cars_score = backup_owner_cars / 10
        backup_total_score = backup_money_score + backup_cars_score
        
        main_money_score = main_owner_balance / 100000
        main_cars_score = main_owner_cars / 10
        main_total_score = main_money_score + main_cars_score
        
        print(f"   📊 Рейтинг текущих данных: {main_total_score:.2f}")
        print(f"   📊 Рейтинг backup: {backup_total_score:.2f}")
        
        # Восстанавливаем если backup имеет ЛУЧШИЙ рейтинг
        if backup_total_score > main_total_score:
            improvement = backup_total_score - main_total_score
            reason = f"сегодняшний backup лучше на {improvement:.2f} баллов"
            print(f"🔄 Восстанавливаю данные ({reason})")
            if restore_from_backup(backup_file):
                save_data()
                print("✅ Восстановление из САМОГО ЛУЧШЕГО сегодняшнего backup завершено!")
            else:
                print("❌ Ошибка восстановления из backup")
        else:
            print("✅ Текущие данные лучше или равны сегодняшнему backup")
            
    except Exception as e:
        print(f"❌ Ошибка при восстановлении: {e}")

@dp.message_handler(lambda m: m.text and is_command_message(m, ['найти backup', 'поиск backup', 'найти бекап']) and m.from_user.id == OWNER_ID)
async def find_all_backups(message: types.Message):
    """Поиск всех backup файлов с информацией"""
    backup_files = glob.glob('backups/bot_data_*.bak')
    if not backup_files:
        await message.reply("❌ Backup файлы не найдены!")
        return
    
    text = "📁 <b>ВСЕ BACKUP ФАЙЛЫ:</b>\n\n"
    
    backup_info = []
    for backup_file in backup_files:
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            total_cars = sum(len(garage) for garage in data.get('user_garage', {}).values())
            total_money = sum(data.get('user_balance', {}).values())
            file_time = os.path.getmtime(backup_file)
            file_date = datetime.fromtimestamp(file_time).strftime('%d.%m.%Y %H:%M')
            
            backup_info.append({
                'file': backup_file,
                'cars': total_cars,
                'money': total_money,
                'date': file_date
            })
            
        except Exception as e:
            backup_info.append({
                'file': backup_file,
                'cars': 0,
                'money': 0,
                'date': 'Ошибка чтения',
                'error': str(e)
            })
    
    backup_info.sort(key=lambda x: x['cars'], reverse=True)
    
    for i, info in enumerate(backup_info[:15], 1):
        status = "🏆" if i == 1 else "📊"
        text += f"{status} <b>{os.path.basename(info['file'])}</b>\n"
        text += f"   📅 {info['date']}\n"
        text += f"   🚗 Машин: {info['cars']}\n"
        text += f"   💰 Денег: {format_money(info['money'])}\n"
        if 'error' in info:
            text += f"   ❌ Ошибка: {info['error']}\n"
        text += "\n"
    
    if len(backup_info) > 15:
        text += f"<i>... и еще {len(backup_info) - 15} backup файлов</i>\n"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        text="🔄 Восстановить из лучшего backup", 
        callback_data="restore_from_best_backup"
    ))
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "restore_from_best_backup")
async def restore_from_best_backup(callback_query: types.CallbackQuery):
    """Восстановление из лучшего backup"""
    await bot.answer_callback_query(callback_query.id)
    
    backup_file = find_best_backup_by_content()
    if not backup_file:
        await bot.send_message(callback_query.from_user.id, "❌ Backup файлы не найдены!")
        return
    
    if restore_from_backup(backup_file):
        save_data()
        
        total_cars = sum(len(garage) for garage in user_garage.values())
        total_money = sum(user_balance.values())
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ <b>ДАННЫЕ ВОССТАНОВЛЕНЫ!</b>\n\n"
            f"📁 Backup: <code>{os.path.basename(backup_file)}</code>\n"
            f"🚗 Машин восстановлено: {total_cars}\n"
            f"💰 Денег восстановлено: {format_money(total_money)}",
            parse_mode='HTML'
        )
    else:
        await bot.send_message(callback_query.from_user.id, "❌ Ошибка восстановления данных!")

def restore_from_backup(backup_file):
    """Восстанавливает данные из backup файла"""
    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        user_balance.clear()
        user_garage.clear()
        car_owner_map.clear()
        user_shop_limits.clear()
        last_use.clear()
        daily_gift.clear()
        user_quests.clear()
        user_achievements.clear()
        promocodes.clear()
        used_promocodes.clear()
        auctions.clear()
        user_bids.clear()
        user_carsharing.clear()
        user_taxipark.clear()
        flea_market.clear()
        user_scrap.clear()
        
        for k, v in backup_data.get('user_balance', {}).items():
            try:
                user_balance[int(k)] = int(v)
            except Exception:
                user_balance[int(k)] = v

        for k, v in backup_data.get('user_garage', {}).items():
            try:
                user_garage[int(k)] = v
            except Exception:
                user_garage[k] = v

        car_owner_map.update(backup_data.get('car_owner_map', {}))

        for k, v in backup_data.get('user_shop_limits', {}).items():
            try:
                lr = v.get('last_reset')
                user_shop_limits[int(k)] = {'count': v.get('count', 0), 'last_reset': datetime.fromisoformat(lr)}
            except Exception:
                user_shop_limits[int(k)] = {'count': v.get('count', 0), 'last_reset': datetime.now()}

        for k, v in backup_data.get('last_use', {}).items():
            try:
                last_use[int(k)] = float(v)
            except Exception:
                last_use[int(k)] = v

        for k, v in backup_data.get('daily_gift', {}).items():
            try:
                daily_gift[int(k)] = float(v)
            except Exception:
                daily_gift[int(k)] = v
                
        for k, v in backup_data.get('user_quests', {}).items():
            user_quests[int(k)] = v
            
        for k, v in backup_data.get('user_achievements', {}).items():
            user_achievements[int(k)] = v
            
        promocodes.update(backup_data.get('promocodes', {}))
        
        for k, v in backup_data.get('used_promocodes', {}).items():
            used_promocodes[int(k)] = v
            
        auctions.update(backup_data.get('auctions', {}))
        
        user_bids.update(backup_data.get('user_bids', {}))

        # Новые системы
        for k, v in backup_data.get('user_carsharing', {}).items():
            user_carsharing[int(k)] = v
            
        for k, v in backup_data.get('user_taxipark', {}).items():
            user_taxipark[int(k)] = v
            
        flea_market.update(backup_data.get('flea_market', {}))
        
        for k, v in backup_data.get('user_scrap', {}).items():
            user_scrap[int(k)] = v

        print(f"✅ Успешно восстановлено из backup: {backup_file}")
        print(f"📊 Статистика восстановления:")
        print(f"   👥 Пользователей: {len(user_balance)}")
        print(f"   🚗 Всего машин: {sum(len(garage) for garage in user_garage.values())}")
        print(f"   💰 Общий баланс: {sum(user_balance.values()):,}$")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка восстановления из backup: {e}")
        return False

@dp.message_handler(lambda m: m.text and is_command_message(m, ['восстановить баланс', 'рестор баланс']) and m.from_user.id == OWNER_ID)
async def force_restore_balance(message: types.Message):
    """Принудительное восстановление из backup с лучшим балансом"""
    await message.reply("🔄 <b>Принудительное восстановление баланса...</b>", parse_mode='HTML')
    await force_restore_if_needed()
    
    total_cars = sum(len(garage) for garage in user_garage.values())
    total_money = sum(user_balance.values())
    owner_balance = user_balance.get(OWNER_ID, 0)
    
    await message.reply(    
        f"✅ <b>Восстановление завершено!</b>\n\n"
        f"💰 Баланс владельца: {format_money(owner_balance)}\n"
        f"🚗 Всего машин: {total_cars}\n"
        f"💵 Общий баланс: {format_money(total_money)}",
        parse_mode='HTML'
    )

async def auto_restore_on_startup():
    """Автоматическое восстановление при запуске"""
    try:
        backup_file = find_latest_backup()
        if not backup_file:
            print("✅ Backup файлы не найдены, используем основной файл")
            return
        
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        backup_cars = sum(len(garage) for garage in backup_data.get('user_garage', {}).values())
        
        main_cars = 0
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                main_data = json.load(f)
            main_cars = sum(len(garage) for garage in main_data.get('user_garage', {}).values())
        
        print(f"📊 Сравнение данных:")
        print(f"   Основной файл: {main_cars} машин")
        print(f"   Backup файл: {backup_cars} машин")
        
        if backup_cars > main_cars:
            print(f"🔄 В backup больше машин! Восстанавливаю из {backup_file}")
            if restore_from_backup(backup_file):
                save_data()
                print("✅ Автоматическое восстановление завершено!")
            else:
                print("❌ Ошибка восстановления из backup")
        else:
            print("✅ Основной файл содержит достаточно данных, восстановление не требуется")
            
    except Exception as e:
        print(f"❌ Ошибка при автоматическом восстановлении: {e}")

# Система квестов
def init_user_quests(user_id: int):
    if user_id not in user_quests:
        user_quests[user_id] = {
            'daily_quests': {},
            'progress': {
                'cars_collected_today': 0,
                'races_won_today': 0,
                'cars_sold_today': 0,
                'cars_tuned_today': 0,
                'cars_crafted_today': 0,
                'auctions_won_today': 0,
                'total_cars_collected': 0,
                'total_races_won': 0,
                'total_money_earned': 0,
                'money_earned_today': 0,
                'total_cars_crafted': 0,
                'total_auctions_won': 0
            },
            'last_reset': datetime.now().timestamp()
        }
        generate_daily_quests(user_id)

def init_user_achievements(user_id: int):
    if user_id not in user_achievements:
        user_achievements[user_id] = {}
        for achievement_id in ACHIEVEMENTS:
            user_achievements[user_id][achievement_id] = {
                'completed': False,
                'progress': 0,
                'completed_at': None
            }

def generate_daily_quests(user_id: int):
    """Генерирует случайные ежедневные задания"""
    available_quests = list(DAILY_QUESTS.keys())
    selected_quests = random.sample(available_quests, min(3, len(available_quests)))
    
    user_quests[user_id]['daily_quests'] = {}
    for quest_id in selected_quests:
        user_quests[user_id]['daily_quests'][quest_id] = {
            'progress': 0,
            'completed': False,
            'claimed': False
        }

def reset_daily_quests_if_needed(user_id: int):
    """Сбрасывает ежедневные задания если прошел день"""
    if user_id in user_quests:
        last_reset = user_quests[user_id]['last_reset']
        if datetime.now().timestamp() - last_reset >= 24 * 60 * 60:
            user_quests[user_id]['progress'] = {
                'cars_collected_today': 0,
                'races_won_today': 0,
                'cars_sold_today': 0,
                'cars_tuned_today': 0,
                'cars_crafted_today': 0,
                'auctions_won_today': 0,
                'total_cars_collected': user_quests[user_id]['progress'].get('total_cars_collected', 0),
                'total_races_won': user_quests[user_id]['progress'].get('total_races_won', 0),
                'total_money_earned': user_quests[user_id]['progress'].get('total_money_earned', 0),
                'total_cars_crafted': user_quests[user_id]['progress'].get('total_cars_crafted', 0),
                'total_auctions_won': user_quests[user_id]['progress'].get('total_auctions_won', 0),
                'money_earned_today': 0
            }
            generate_daily_quests(user_id)
            user_quests[user_id]['last_reset'] = datetime.now().timestamp()
            save_data()

def update_quest_progress(user_id: int, quest_type: str, amount: int = 1):
    """Обновляет прогресс заданий"""
    init_user_quests(user_id)
    reset_daily_quests_if_needed(user_id)
    
    progress_keys = ['cars_collected_today', 'races_won_today', 'cars_sold_today', 
                    'cars_tuned_today', 'cars_crafted_today', 'auctions_won_today',
                    'total_cars_collected', 'total_races_won', 'total_money_earned', 
                    'money_earned_today', 'total_cars_crafted', 'total_auctions_won']
    
    for key in progress_keys:
        if key not in user_quests[user_id]['progress']:
            user_quests[user_id]['progress'][key] = 0
    
    if quest_type == 'car_collected':
        user_quests[user_id]['progress']['cars_collected_today'] += amount
        user_quests[user_id]['progress']['total_cars_collected'] += amount
    elif quest_type == 'race_won':
        user_quests[user_id]['progress']['races_won_today'] += amount
        user_quests[user_id]['progress']['total_races_won'] += amount
    elif quest_type == 'car_sold':
        user_quests[user_id]['progress']['cars_sold_today'] += amount
    elif quest_type == 'car_tuned':
        user_quests[user_id]['progress']['cars_tuned_today'] += amount
    elif quest_type == 'car_crafted':
        user_quests[user_id]['progress']['cars_crafted_today'] += amount
        user_quests[user_id]['progress']['total_cars_crafted'] += amount
    elif quest_type == 'auction_won':
        user_quests[user_id]['progress']['auctions_won_today'] += amount
        user_quests[user_id]['progress']['total_auctions_won'] += amount
    elif quest_type == 'money_earned':
        user_quests[user_id]['progress']['total_money_earned'] += amount
        user_quests[user_id]['progress']['money_earned_today'] += amount
    
    for quest_id, quest_data in user_quests[user_id]['daily_quests'].items():
        if not quest_data['completed']:
            quest_info = DAILY_QUESTS[quest_id]
            if quest_id == 'collect_cars' and quest_type == 'car_collected':
                user_quests[user_id]['daily_quests'][quest_id]['progress'] += amount
            elif quest_id == 'win_races' and quest_type == 'race_won':
                user_quests[user_id]['daily_quests'][quest_id]['progress'] += amount
            elif quest_id == 'sell_cars' and quest_type == 'car_sold':
                user_quests[user_id]['daily_quests'][quest_id]['progress'] += amount
            elif quest_id == 'tune_car' and quest_type == 'car_tuned':
                user_quests[user_id]['daily_quests'][quest_id]['progress'] += amount
            elif quest_id == 'craft_car' and quest_type == 'car_crafted':
                user_quests[user_id]['daily_quests'][quest_id]['progress'] += amount
            elif quest_id == 'win_auction' and quest_type == 'auction_won':
                user_quests[user_id]['daily_quests'][quest_id]['progress'] += amount
            elif quest_id == 'daily_balance' and quest_type == 'money_earned':
                user_quests[user_id]['daily_quests'][quest_id]['progress'] += amount
            
            if user_quests[user_id]['daily_quests'][quest_id]['progress'] >= quest_info['target']:
                user_quests[user_id]['daily_quests'][quest_id]['completed'] = True
    
    update_achievements(user_id)
    save_data()

def update_achievements(user_id: int):
    """Обновляет прогресс достижений"""
    init_user_achievements(user_id)
    progress = user_quests[user_id]['progress']
    
    achievements_to_update = {
        'first_car': progress['total_cars_collected'] >= 1,
        'garage_king': progress['total_cars_collected'] >= 10,
        'race_champion': progress['total_races_won'] >= 10,
        'millionaire': progress['total_money_earned'] >= 1000000,
        'car_collector': progress['total_cars_collected'] >= 25,
        'legend_owner': sum(1 for car in user_garage.get(user_id, []) if car.get('rarity') == 'Легендарные') >= 5,
        'master_crafter': progress['total_cars_crafted'] >= 10,
        'auction_king': progress['total_auctions_won'] >= 5
    }
    
    for achievement_id, completed in achievements_to_update.items():
        if achievement_id not in user_achievements[user_id]:
            user_achievements[user_id][achievement_id] = {
                'completed': False,
                'progress': 0,
                'completed_at': None
            }
        
        if completed and not user_achievements[user_id][achievement_id]['completed']:
            user_achievements[user_id][achievement_id]['completed'] = True
            user_achievements[user_id][achievement_id]['completed_at'] = datetime.now().timestamp()
            user_balance[user_id] += ACHIEVEMENTS[achievement_id]['reward']
            save_data()

# Команды для квестов
@dp.message_handler(lambda m: m.text and is_command_message(m, ['квесты', 'задания', 'quests']))
async def show_quests(message: types.Message):
    user_id = message.from_user.id
    init_user_quests(user_id)
    reset_daily_quests_if_needed(user_id)
    
    text = "🎯 <b>ЕЖЕДНЕВНЫЕ ЗАДАНИЯ</b>\n\n"
    
    completed_count = 0
    for quest_id, quest_data in user_quests[user_id]['daily_quests'].items():
        quest_info = DAILY_QUESTS[quest_id]
        progress = quest_data['progress']
        target = quest_info['target']
        
        status = "✅" if quest_data['completed'] else "🔄"
        if quest_data['completed']:
            completed_count += 1
            
        text += f"{status} <b>{quest_info['name']}</b>\n"
        text += f"   {quest_info['description']}\n"
        text += f"   Прогресс: {progress}/{target}\n"
        text += f"   Награда: {quest_info['reward']:,}$\n\n"
    
    kb = types.InlineKeyboardMarkup()
    if completed_count > 0:
        kb.add(types.InlineKeyboardButton(text=f"🎁 Получить награды ({completed_count})", callback_data="claim_quest_rewards"))
    
    kb.add(types.InlineKeyboardButton(text="🏆 Достижения", callback_data="show_achievements"))
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.message_handler(lambda m: m.text and is_command_message(m, ['достижения', 'achievements']))
async def show_achievements_cmd(message: types.Message):
    user_id = message.from_user.id
    init_user_achievements(user_id)
    
    text = "🏆 <b>ДОСТИЖЕНИЯ</b>\n\n"
    
    completed_count = 0
    total_count = len(ACHIEVEMENTS)
    
    for achievement_id, achievement_info in ACHIEVEMENTS.items():
        if achievement_id not in user_achievements[user_id]:
            user_achievements[user_id][achievement_id] = {
                'completed': False,
                'progress': 0,
                'completed_at': None
            }
            
        user_achievement = user_achievements[user_id][achievement_id]
        progress = user_quests[user_id]['progress']
        
        if achievement_id == 'first_car':
            current_progress = min(progress['total_cars_collected'], achievement_info['target'])
        elif achievement_id == 'garage_king':
            current_progress = min(progress['total_cars_collected'], achievement_info['target'])
        elif achievement_id == 'race_champion':
            current_progress = min(progress['total_races_won'], achievement_info['target'])
        elif achievement_id == 'millionaire':
            current_progress = min(progress['total_money_earned'], achievement_info['target'])
        elif achievement_id == 'car_collector':
            current_progress = min(progress['total_cars_collected'], achievement_info['target'])
        elif achievement_id == 'legend_owner':
            current_progress = min(sum(1 for car in user_garage.get(user_id, []) if car.get('rarity') == 'Легендарные'), achievement_info['target'])
        elif achievement_id == 'master_crafter':
            current_progress = min(progress['total_cars_crafted'], achievement_info['target'])
        elif achievement_id == 'auction_king':
            current_progress = min(progress['total_auctions_won'], achievement_info['target'])
        else:
            current_progress = 0
            
        status = "✅" if user_achievement['completed'] else "🔄"
        if user_achievement['completed']:
            completed_count += 1
            
        text += f"{status} <b>{achievement_info['name']}</b>\n"
        text += f"   {achievement_info['description']}\n"
        text += f"   Прогресс: {current_progress}/{achievement_info['target']}\n"
        text += f"   Награда: {achievement_info['reward']:,}$\n\n"
    
    text += f"📊 Выполнено: {completed_count}/{total_count}"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text="🎯 Задания", callback_data="show_quests"))
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "show_quests")
async def callback_show_quests(callback_query: types.CallbackQuery):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    init_user_quests(user_id)
    reset_daily_quests_if_needed(user_id)
    
    text = "🎯 <b>ЕЖЕДНЕВНЫЕ ЗАДАНИЯ</b>\n\n"
    
    completed_count = 0
    for quest_id, quest_data in user_quests[user_id]['daily_quests'].items():
        quest_info = DAILY_QUESTS[quest_id]
        progress = quest_data['progress']
        target = quest_info['target']
        
        status = "✅" if quest_data['completed'] else "🔄"
        if quest_data['completed']:
            completed_count += 1
            
        text += f"{status} <b>{quest_info['name']}</b>\n"
        text += f"   {quest_info['description']}\n"
        text += f"   Прогресс: {progress}/{target}\n"
        text += f"   Награда: {quest_info['reward']:,}$\n\n"
    
    kb = types.InlineKeyboardMarkup()
    if completed_count > 0:
        kb.add(types.InlineKeyboardButton(text=f"🎁 Получить награды ({completed_count})", callback_data="claim_quest_rewards"))
    
    kb.add(types.InlineKeyboardButton(text="🏆 Достижения", callback_data="show_achievements"))
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            parse_mode='HTML',
            reply_markup=kb
        )
    except:
        await bot.send_message(callback_query.message.chat.id, text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "show_achievements")
async def callback_show_achievements(callback_query: types.CallbackQuery):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    init_user_achievements(user_id)
    
    text = "🏆 <b>ДОСТИЖЕНИЯ</b>\n\n"
    
    completed_count = 0
    total_count = len(ACHIEVEMENTS)
    
    for achievement_id, achievement_info in ACHIEVEMENTS.items():
        if achievement_id not in user_achievements[user_id]:
            user_achievements[user_id][achievement_id] = {
                'completed': False,
                'progress': 0,
                'completed_at': None
            }
            
        user_achievement = user_achievements[user_id][achievement_id]
        progress = user_quests[user_id]['progress']
        
        if achievement_id == 'first_car':
            current_progress = min(progress['total_cars_collected'], achievement_info['target'])
        elif achievement_id == 'garage_king':
            current_progress = min(progress['total_cars_collected'], achievement_info['target'])
        elif achievement_id == 'race_champion':
            current_progress = min(progress['total_races_won'], achievement_info['target'])
        elif achievement_id == 'millionaire':
            current_progress = min(progress['total_money_earned'], achievement_info['target'])
        elif achievement_id == 'car_collector':
            current_progress = min(progress['total_cars_collected'], achievement_info['target'])
        elif achievement_id == 'legend_owner':
            current_progress = min(sum(1 for car in user_garage.get(user_id, []) if car.get('rarity') == 'Легендарные'), achievement_info['target'])
        elif achievement_id == 'master_crafter':
            current_progress = min(progress['total_cars_crafted'], achievement_info['target'])
        elif achievement_id == 'auction_king':
            current_progress = min(progress['total_auctions_won'], achievement_info['target'])
        else:
            current_progress = 0
            
        status = "✅" if user_achievement['completed'] else "🔄"
        if user_achievement['completed']:
            completed_count += 1
            
        text += f"{status} <b>{achievement_info['name']}</b>\n"
        text += f"   {achievement_info['description']}\n"
        text += f"   Прогресс: {current_progress}/{achievement_info['target']}\n"
        text += f"   Награда: {achievement_info['reward']:,}$\n\n"
    
    text += f"📊 Выполнено: {completed_count}/{total_count}"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text="🎯 Задания", callback_data="show_quests"))
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            parse_mode='HTML',
            reply_markup=kb
        )
    except:
        await bot.send_message(callback_query.message.chat.id, text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "claim_quest_rewards")
async def claim_quest_rewards(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    total_reward = 0
    claimed_count = 0
    
    for quest_id, quest_data in user_quests[user_id]['daily_quests'].items():
        if quest_data['completed'] and not quest_data['claimed']:
            reward = DAILY_QUESTS[quest_id]['reward']
            total_reward += reward
            user_quests[user_id]['daily_quests'][quest_id]['claimed'] = True
            claimed_count += 1
    
    if total_reward > 0:
        user_balance[user_id] += total_reward
        update_quest_progress(user_id, 'money_earned', total_reward)
        save_data()
        
        await callback_query.answer(f"🎉 Получено {claimed_count} наград! +{total_reward:,}$", show_alert=True)
        await callback_show_quests(callback_query)
    else:
        await callback_query.answer("❌ Нет доступных наград для получения", show_alert=True)

def generate_unique_id(length=8): 
    while True: 
        uid = ''.join(random.choice(string.ascii_letters+string.digits) for _ in range(length)) 
        if uid not in car_owner_map: return uid 

def format_money(amount: int) -> str: 
    try: 
        return f"{amount:,}$".replace(',', ' ') 
    except Exception: 
        return f"{amount}$" 

def ensure_user_initialized(user_id:int): 
    changed = False 
    if user_id not in user_balance: user_balance[user_id]=10000; changed=True 
    if user_id not in user_garage: user_garage[user_id]=[]; changed=True 
    if user_id not in user_shop_limits: user_shop_limits[user_id]={'count':0,'last_reset':datetime.now()}; changed=True 
    if (datetime.now()-user_shop_limits[user_id]['last_reset']).days>=1: 
        user_shop_limits[user_id]={'count':0,'last_reset':datetime.now()}; changed=True 
    
    # Инициализация квестов если нужно
    init_user_quests(user_id)
    init_user_achievements(user_id)
    
    # Инициализация новых систем
    if user_id not in user_scrap:
        user_scrap[user_id] = 0
        changed = True
        
    if changed: save_data() 

def is_giveaway_active() -> bool:
    return bool(active_giveaway.get('active', False) and active_giveaway.get('end_time', 0) > time.time())

def giveaway_participant_count() -> int:
    return len(giveaway_participants)

def add_giveaway_participant(user_id: int) -> None:
    giveaway_participants[user_id] = {'joined_at': time.time(), 'note': None}
    save_data()

def is_command_message(m: types.Message, keywords):
    """Return True if message text exactly equals a keyword or starts with keyword+space"""
    if not m.text:
        return False
    txt = m.text.strip().lower()
    for w in keywords:
        w = w.strip().lower()
        if txt == w or txt.startswith(w + ' '):
            return True
    return False

def format_giveaway_text(g):
    prizes_text = '\n'.join([f"{i+1} место: {prize}" for i, prize in enumerate(g.get('prizes', []))])
    end_dt = datetime.fromtimestamp(g['end_time']) if g.get('end_time') else None
    end_text = end_dt.strftime('%d.%m.%Y %H:%M') if end_dt else '—'
    return (
        f"🎉 <b>РОЗЫГРЫШ ЗАПУЩЕН!</b> 🎉\n\n"
        f"📝 <b>{g.get('description','')}</b>\n\n"
        f"🎁 <b>Призы:</b>\n{prizes_text}\n\n"
        f"👥 Участие: {g.get('winner_count', 1)} победителей\n"
        f"💰 Мин. баланс: {format_money(g.get('min_balance',0))}\n"
        f"⏰ Окончание: {end_text}\n\n"
        f"💡 Для участия напишите: <code>+рз</code>"
    )

def grant_subscription(user_id: int, days: int | None = None, reason: str = 'manual'):
    """Grant subscription to user_id for days (None = permanent)"""
    expires_at = None
    if days and days > 0:
        expires_at = time.time() + days * 86400
    user_subscriptions[user_id] = {'expires_at': expires_at, 'type': reason}
    save_data()

def revoke_subscription(user_id: int):
    if user_id in user_subscriptions:
        del user_subscriptions[user_id]
        save_data()

async def is_user_subscribed(user_id: int) -> bool:
    """Проверяет, есть ли действующая подписка у пользователя.
    1) Проверяем локальные записи `user_subscriptions` (expires_at)
    2) При наличии `SUBS_CHANNEL_ID` проверяем членство в канале/чате
    """
    try:
        sub = user_subscriptions.get(user_id)
        if sub:
            expires = sub.get('expires_at')
            if not expires or time.time() < expires:
                return True

        if SUBS_CHANNEL_ID:
            try:
                member = await bot.get_chat_member(SUBS_CHANNEL_ID, user_id)
                if member and member.status not in ['left', 'kicked']:
                    return True
            except Exception:
                # Не можем проверить (например, приватный канал), продолжим
                pass

    except Exception:
        pass
    return False

def generate_car_data(car_name:str,rarity:str,user_id:int): 
    car_id = generate_unique_id() 
    value = random.randint(*RARITY_VALUES.get(rarity, (10000,50000))) 

    STAT_RANGES = { 
        'Обычные': {'hp':(80,150),'acc':(30,60),'handling':(30,60)}, 
        'Редкие': {'hp':(140,260),'acc':(50,80),'handling':(50,80)}, 
        'Эпические': {'hp':(250,450),'acc':(70,95),'handling':(70,95)}, 
        'Легендарные': {'hp':(400,900),'acc':(85,100),'handling':(80,100)}, 
        'Эксклюзивные': {'hp':(800,1500),'acc':(90,100),'handling':(90,100)},
        'Скраповые': {'hp':(200,400),'acc':(40,70),'handling':(40,70)}
    } 

    ranges = STAT_RANGES.get(rarity, STAT_RANGES['Обычные']) 
    hp = random.randint(*ranges['hp']) 
    acc = random.randint(*ranges['acc']) 
    handling = random.randint(*ranges['handling']) 

    image_filename = CAR_FILE_MAPPING.get(car_name, 'default.png')
    image_path = IMAGE_BASE_PATH + image_filename
    
    car_owner_map[car_id]=user_id 
    sellable = False if rarity == 'Эксклюзивные' else True 
    
    # Добавляем износ для машины (от 100% до 0%)
    wear = 100  # начальный износ 100%
    
    return { 
        'id':car_id, 
        'name':car_name, 
        'rarity':RARITY_MAP.get(rarity, rarity), 
        'rarity_key':rarity, 
        'value':value, 
        'image_path':image_path, 
        'hp':hp, 
        'acc':acc, 
        'handling':handling, 
        'sellable': sellable,
        'wear': wear  # новый параметр износа
    } 

# ========== СИСТЕМА КРАФТА ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['крафт', 'craft']))
async def craft_command(message: types.Message):
    """Команда для крафта машин"""
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    # Subscription check: блокируем крафт для не подписанных пользователей
    try:
        if not await is_user_subscribed(user_id):
            await message.reply("❌ Крафт доступен только подписчикам. Чтобы получить доступ, подпишитесь на наш канал или свяжитесь с администратором.")
            return
    except Exception:
        # Не смогли проверить подписку — по умолчанию блокируем
        await message.reply("❌ Не удалось проверить подписку. Попробуйте позже.")
        return
    
    cars_list = user_garage.get(user_id, [])
    scrap_count = user_scrap.get(user_id, 0)
    
    text = (
        "🔨 <b>СИСТЕМА КРАФТА МАШИН</b>\n\n"
        "Объединяйте машины для создания более крутых моделей!\n\n"
        f"🔩 <b>Ваш скрап:</b> {scrap_count} единиц\n\n"
        "📊 <b>Доступные рецепты:</b>\n"
    )
    
    for recipe_id, recipe in crafting_recipes.items():
        success_rate = f"🎯 Шанс: {recipe['success_chance']}%"
        cost = f"💰 Стоимость: {format_money(recipe['cost'])}"
        text += f"• {recipe['name']} - {success_rate} - {cost}\n"
    
    text += "\n💡 Выберите рецепт для крафта:"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for recipe_id, recipe in crafting_recipes.items():
        kb.add(types.InlineKeyboardButton(
            text=f"🔨 {recipe['name']}",
            callback_data=f"craft_select:{recipe_id}"
        ))
    
    kb.add(types.InlineKeyboardButton(text="🔄 Разобрать машину", callback_data="scrap_car"))
    kb.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="craft_cancel"))
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "scrap_car")
async def scrap_car_menu(callback_query: types.CallbackQuery):
    """Меню для разбора машин на скрап"""
    user_id = callback_query.from_user.id
    ensure_user_initialized(user_id)
    
    cars_list = user_garage.get(user_id, [])
    if not cars_list:
        await bot.answer_callback_query(callback_query.id, "❌ У вас нет машин для разбора!", show_alert=True)
        return
    
    text = "🔄 <b>РАЗБОР МАШИНЫ НА СКРАП</b>\n\nВыберите машину для разбора:\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    for car in cars_list:
        if car.get('sellable', True):  # Можно разбирать только продаваемые машины
            scrap_value = max(1, car['value'] // 10000)  # 1 скрап за каждые 10к стоимости
            kb.add(types.InlineKeyboardButton(
                text=f"🔩 {car['name']} ({car['rarity']}) → {scrap_value} скрапа",
                callback_data=f"scrap_confirm:{car['id']}"
            ))
    
    kb.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="craft_back"))
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML',
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('scrap_confirm:'))
async def scrap_confirm(callback_query: types.CallbackQuery):
    """Подтверждение разбора машины"""
    user_id = callback_query.from_user.id
    car_id = callback_query.data.split(':', 1)[1]
    
    cars_list = user_garage.get(user_id, [])
    car_to_scrap = None
    
    for i, car in enumerate(cars_list):
        if car.get('id') == car_id:
            car_to_scrap = cars_list.pop(i)
            break
    
    if not car_to_scrap:
        await bot.answer_callback_query(callback_query.id, "❌ Машина не найдена!", show_alert=True)
        return
    
    # Вычисляем количество скрапа
    scrap_value = max(1, car_to_scrap['value'] // 10000)
    user_scrap[user_id] = user_scrap.get(user_id, 0) + scrap_value
    
    # Удаляем машину из системы
    if car_id in car_owner_map:
        del car_owner_map[car_id]
    
    save_data()
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"✅ <b>МАШИНА РАЗОБРАНА!</b>\n\n"
             f"🚗 {car_to_scrap['name']} ({car_to_scrap['rarity']})\n"
             f"🔩 Получено скрапа: +{scrap_value}\n"
             f"📦 Всего скрапа: {user_scrap[user_id]}\n\n"
             f"💡 Используйте скрап для создания уникальных машин!",
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('craft_select:'))
async def craft_select_recipe(callback_query: types.CallbackQuery):
    """Выбор рецепта для крафта"""
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    recipe_id = callback_query.data.split(':', 1)[1]
    
    if recipe_id not in crafting_recipes:
        await bot.send_message(user_id, "❌ Рецепт не найден!")
        return
    
    recipe = crafting_recipes[recipe_id]
    # Проверка на премиум-рецепт
    if recipe.get('premium'):
        try:
            if not await is_user_subscribed(user_id):
                await bot.send_message(user_id, "❌ Этот рецепт доступен только подписчикам.")
                return
        except Exception:
            await bot.send_message(user_id, "❌ Не удалось проверить подписку. Попробуйте позже.")
            return
    
    # Проверяем специальные условия для скрапа
    if recipe['input_rarity'] == 'Скрап':
        scrap_count = user_scrap.get(user_id, 0)
        required_scrap = recipe['input_count']
        
        if scrap_count < required_scrap:
            await bot.send_message(
                user_id,
                f"❌ Недостаточно скрапа!\n"
                f"Нужно: {required_scrap} скрапа\n"
                f"У вас: {scrap_count} скрапа"
            )
            return
        
        # Для скрапа не нужен выбор машин
        if user_balance.get(user_id, 0) < recipe['cost']:
            await bot.send_message(
                user_id,
                f"❌ Недостаточно средств!\n"
                f"Нужно: {format_money(recipe['cost'])}\n"
                f"Ваш баланс: {format_money(user_balance.get(user_id, 0))}"
            )
            return
        
        text = (
            f"🔨 <b>ПОДТВЕРЖДЕНИЕ КРАФТА</b>\n\n"
            f"📝 Рецепт: <b>{recipe['name']}</b>\n"
            f"📋 Описание: {recipe['description']}\n"
            f"🎯 Шанс успеха: <b>{recipe['success_chance']}%</b>\n"
            f"💰 Стоимость: <b>{format_money(recipe['cost'])}</b>\n\n"
            f"🔩 Используется скрапа: {required_scrap}\n"
            f"⚙️ Результат: машина редкости <b>{recipe['output_rarity']}</b>"
        )
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(
            text="✅ Начать крафт",
            callback_data=f"craft_confirm_scrap:{recipe_id}:{required_scrap}"
        ))
        kb.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="craft_back"))
        
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            parse_mode='HTML',
            reply_markup=kb
        )
        return
    
    # Обычный крафт из машин
    cars_list = user_garage.get(user_id, [])
    available_cars = []
    
    if isinstance(recipe['input_rarity'], list):
        required_cars = []
        for i, rarity in enumerate(recipe['input_rarity']):
            count = recipe['input_count'][i]
            cars_of_rarity = [car for car in cars_list if car.get('rarity_key') == rarity]
            if len(cars_of_rarity) < count:
                await bot.send_message(
                    user_id,
                    f"❌ Недостаточно машин для крафта!\n"
                    f"Нужно {count} машин редкости '{rarity}', а у вас {len(cars_of_rarity)}"
                )
                return
            required_cars.extend(cars_of_rarity[:count])
        available_cars = required_cars
    else:
        required_rarity = recipe['input_rarity']
        required_count = recipe['input_count']
        available_cars = [car for car in cars_list if car.get('rarity_key') == required_rarity]
        
        if len(available_cars) < required_count:
            await bot.send_message(
                user_id,
                f"❌ Недостаточно машин для крафта!\n"
                f"Нужно {required_count} машин редкости '{required_rarity}', а у вас {len(available_cars)}"
            )
            return
        available_cars = available_cars[:required_count]
    
    if user_balance.get(user_id, 0) < recipe['cost']:
        await bot.send_message(
            user_id,
            f"❌ Недостаточно средств!\n"
            f"Нужно: {format_money(recipe['cost'])}\n"
            f"Ваш баланс: {format_money(user_balance.get(user_id, 0))}"
        )
        return
    
    text = (
        f"🔨 <b>ПОДТВЕРЖДЕНИЕ КРАФТА</b>\n\n"
        f"📝 Рецепт: <b>{recipe['name']}</b>\n"
        f"📋 Описание: {recipe['description']}\n"
        f"🎯 Шанс успеха: <b>{recipe['success_chance']}%</b>\n"
        f"💰 Стоимость: <b>{format_money(recipe['cost'])}</b>\n\n"
        f"🚗 Используемые машины:\n"
    )
    
    for car in available_cars:
        text += f"• {car['name']} ({car['rarity']})\n"
    
    text += f"\n⚙️ Результат: машина редкости <b>{recipe['output_rarity']}</b>"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        text="✅ Начать крафт",
        callback_data=f"craft_confirm:{recipe_id}:{','.join(car['id'] for car in available_cars)}"
    ))
    kb.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="craft_back"))
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML',
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('craft_confirm_scrap:'))
async def craft_confirm_scrap(callback_query: types.CallbackQuery):
    """Подтверждение крафта из скрапа"""
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    parts = callback_query.data.split(':')
    recipe_id = parts[1]
    scrap_count = int(parts[2])
    
    if recipe_id not in crafting_recipes:
        await bot.send_message(user_id, "❌ Рецепт не найден!")
        return
    
    recipe = crafting_recipes[recipe_id]
    
    if user_scrap.get(user_id, 0) < scrap_count:
        await bot.send_message(user_id, "❌ Недостаточно скрапа!")
        return
    
    if user_balance.get(user_id, 0) < recipe['cost']:
        await bot.send_message(user_id, "❌ Недостаточно средств!")
        return
    
    crafting_text = "🔨 <b>ПРОЦЕСС КРАФТА</b>\n\n"
    crafting_text += "🔄 Собираем компоненты..."
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=crafting_text,
            parse_mode='HTML'
        )
        await asyncio.sleep(1)
        
        crafting_text += "\n⚙️ Переплавляем скрап..."
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=crafting_text,
            parse_mode='HTML'
        )
        await asyncio.sleep(1)
        
        crafting_text += "\n🎨 Создаём уникальный дизайн..."
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=crafting_text,
            parse_mode='HTML'
        )
        await asyncio.sleep(1)
    except:
        pass
    
    is_success = random.randint(1, 100) <= recipe['success_chance']
    
    if is_success:
        user_balance[user_id] -= recipe['cost']
        user_scrap[user_id] -= scrap_count
        
        output_rarity = recipe['output_rarity']
        available_cars = get_cars_with_events().get(output_rarity, [])
        if available_cars:
            new_car_name = random.choice(available_cars)
            new_car = generate_car_data(new_car_name, output_rarity, user_id)
            user_garage[user_id].append(new_car)
            
            update_quest_progress(user_id, 'car_crafted', 1)
            update_quest_progress(user_id, 'car_collected', 1)
            
            save_data()
            
            success_text = (
                f"🎉 <b>КРАФТ УСПЕШЕН!</b>\n\n"
                f"🚗 Вы создали: <b>{new_car['name']}</b>\n"
                f"💎 Редкость: <b>{new_car['rarity']}</b>\n"
                f"💵 Стоимость: <b>{format_money(new_car['value'])}</b>\n"
                f"⚙️ Характеристики: HP {new_car['hp']} | ACC {new_car['acc']} | HND {new_car['handling']}\n\n"
                f"💰 Потрачено: {format_money(recipe['cost'])}\n"
                f"🔩 Использовано скрапа: {scrap_count}\n"
                f"💳 Баланс: {format_money(user_balance[user_id])}"
            )
            
            try:
                if new_car.get('image_path') and os.path.exists(new_car.get('image_path')):
                    with open(new_car['image_path'], 'rb') as photo:
                        await bot.send_photo(
                            callback_query.message.chat.id,
                            photo,
                            caption=success_text,
                            parse_mode='HTML'
                        )
                else:
                    await bot.send_message(
                        callback_query.message.chat.id,
                        success_text,
                        parse_mode='HTML'
                    )
            except:
                await bot.send_message(
                    callback_query.message.chat.id,
                    success_text,
                    parse_mode='HTML'
                )
        else:
            await bot.send_message(user_id, "❌ Ошибка: нет доступных машин для создания!")
    else:
        user_balance[user_id] -= recipe['cost'] // 2
        user_scrap[user_id] -= scrap_count // 2  # Возвращаем часть скрапа
        
        failure_text = (
            f"💥 <b>КРАФТ ПРОВАЛЕН!</b>\n\n"
            f"К сожалению, что-то пошло не так в процессе создания...\n\n"
            f"💰 Возвращено: {format_money(recipe['cost'] // 2)}\n"
            f"🔩 Возвращено скрапа: {scrap_count // 2}\n"
            f"💳 Баланс: {format_money(user_balance[user_id])}\n\n"
            f"💡 Попробуйте еще раз!"
        )
        
        save_data()
        await bot.send_message(
            callback_query.message.chat.id,
            failure_text,
            parse_mode='HTML'
        )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('craft_confirm:'))
async def craft_confirm(callback_query: types.CallbackQuery):
    """Подтверждение и выполнение крафта"""
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    parts = callback_query.data.split(':')
    recipe_id = parts[1]
    car_ids = parts[2].split(',')
    
    if recipe_id not in crafting_recipes:
        await bot.send_message(user_id, "❌ Рецепт не найден!")
        return
    
    recipe = crafting_recipes[recipe_id]
    cars_list = user_garage.get(user_id, [])
    
    craft_cars = []
    for car_id in car_ids:
        car = next((c for c in cars_list if c.get('id') == car_id), None)
        if not car:
            await bot.send_message(user_id, "❌ Одна из машин больше не доступна!")
            return
        craft_cars.append(car)
    
    if user_balance.get(user_id, 0) < recipe['cost']:
        await bot.send_message(user_id, "❌ Недостаточно средств!")
        return
    
    crafting_text = "🔨 <b>ПРОЦЕСС КРАФТА</b>\n\n"
    crafting_text += "🔄 Собираем компоненты..."
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=crafting_text,
            parse_mode='HTML'
        )
        await asyncio.sleep(1)
        
        crafting_text += "\n⚙️ Настраиваем двигатель..."
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=crafting_text,
            parse_mode='HTML'
        )
        await asyncio.sleep(1)
        
        crafting_text += "\n🎨 Применяем дизайн..."
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=crafting_text,
            parse_mode='HTML'
        )
        await asyncio.sleep(1)
    except:
        pass
    
    is_success = random.randint(1, 100) <= recipe['success_chance']
    
    if is_success:
        user_balance[user_id] -= recipe['cost']
        
        for car in craft_cars:
            user_garage[user_id] = [c for c in user_garage[user_id] if c.get('id') != car.get('id')]
            if car.get('id') in car_owner_map:
                del car_owner_map[car.get('id')]
        
        output_rarity = recipe['output_rarity']
        available_cars = get_cars_with_events().get(output_rarity, [])
        if available_cars:
            new_car_name = random.choice(available_cars)
            new_car = generate_car_data(new_car_name, output_rarity, user_id)
            user_garage[user_id].append(new_car)
            
            update_quest_progress(user_id, 'car_crafted', 1)
            update_quest_progress(user_id, 'car_collected', 1)
            
            save_data()
            
            success_text = (
                f"🎉 <b>КРАФТ УСПЕШЕН!</b>\n\n"
                f"🚗 Вы создали: <b>{new_car['name']}</b>\n"
                f"💎 Редкость: <b>{new_car['rarity']}</b>\n"
                f"💵 Стоимость: <b>{format_money(new_car['value'])}</b>\n"
                f"⚙️ Характеристики: HP {new_car['hp']} | ACC {new_car['acc']} | HND {new_car['handling']}\n\n"
                f"💰 Потрачено: {format_money(recipe['cost'])}\n"
                f"💳 Баланс: {format_money(user_balance[user_id])}"
            )
            
            try:
                if new_car.get('image_path') and os.path.exists(new_car.get('image_path')):
                    with open(new_car['image_path'], 'rb') as photo:
                        await bot.send_photo(
                            callback_query.message.chat.id,
                            photo,
                            caption=success_text,
                            parse_mode='HTML'
                        )
                else:
                    await bot.send_message(
                        callback_query.message.chat.id,
                        success_text,
                        parse_mode='HTML'
                    )
            except:
                await bot.send_message(
                    callback_query.message.chat.id,
                    success_text,
                    parse_mode='HTML'
                )
        else:
            await bot.send_message(user_id, "❌ Ошибка: нет доступных машин для создания!")
    else:
        user_balance[user_id] -= recipe['cost'] // 2
        
        failure_text = (
            f"💥 <b>КРАФТ ПРОВАЛЕН!</b>\n\n"
            f"К сожалению, что-то пошло не так в процессе создания...\n\n"
            f"💰 Возвращено: {format_money(recipe['cost'] // 2)}\n"
            f"💳 Баланс: {format_money(user_balance[user_id])}\n\n"
            f"💡 Машины остались в вашем гараже. Попробуйте еще раз!"
        )
        
        save_data()
        await bot.send_message(
            callback_query.message.chat.id,
            failure_text,
            parse_mode='HTML'
        )

@dp.callback_query_handler(lambda c: c.data == "craft_back")
async def craft_back(callback_query: types.CallbackQuery):
    """Назад в меню крафта"""
    message = callback_query.message
    message.from_user = callback_query.from_user
    await craft_command(message)

@dp.callback_query_handler(lambda c: c.data == "craft_cancel")
async def craft_cancel(callback_query: types.CallbackQuery):
    """Отмена крафта"""
    await bot.answer_callback_query(callback_query.id)
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="❌ Крафт отменен.",
        parse_mode='HTML'
    )

# ========== УЛУЧШЕННЫЙ ГАРАЖ С ИЗНОСОМ ==========

def create_garage_keyboard(index: int, total: int, car_id: str) -> types.InlineKeyboardMarkup: 
    kb = types.InlineKeyboardMarkup(row_width=3) 
    buttons = [] 
    if total > 1: 
        prev_index = (index - 1) % total 
        next_index = (index + 1) % total 
        buttons.append(types.InlineKeyboardButton(text='⬅️', callback_data=f'garage_nav:{prev_index}')) 
        buttons.append(types.InlineKeyboardButton(text=f'{index+1}/{total}', callback_data='garage_ignore')) 
        buttons.append(types.InlineKeyboardButton(text='➡️', callback_data=f'garage_nav:{next_index}')) 
    else:
        buttons.append(types.InlineKeyboardButton(text='1/1', callback_data='garage_ignore')) 

    kb.row(*buttons) 
    kb.row(
        types.InlineKeyboardButton(text=f'💰 Продать', callback_data=f'sell_id:{car_id}'),
        types.InlineKeyboardButton(text=f'🔧 Тюнинг', callback_data=f'tune_select:{car_id}')
    )
    kb.row(
        types.InlineKeyboardButton(text=f'📊 Барахолка', callback_data=f'flea_add:{car_id}'),
        types.InlineKeyboardButton(text=f'🚗 Каршеринг', callback_data=f'carsharing_add:{car_id}')
    )
    return kb 

def get_wear_emoji(wear: int) -> str:
    """Возвращает эмодзи в зависимости от износа"""
    if wear >= 80:
        return "🟢"  # Отличное состояние
    elif wear >= 60:
        return "🟡"  # Хорошее состояние
    elif wear >= 40:
        return "🟠"  # Среднее состояние
    elif wear >= 20:
        return "🔴"  # Плохое состояние
    else:
        return "💀"  # Критическое состояние

async def send_car_card(chat_id: int, car: dict, index: int, total: int, reply_to: types.Message = None, edit_message: dict = None): 
    decorations = get_event_decorations()
    
    wear = car.get('wear', 100)
    wear_emoji = get_wear_emoji(wear)
    
    caption = ( 
        f"{decorations['garage_emoji']} <b>Гараж ({total} шт.)</b>\n\n"
        f"<b>{car['name']}</b> — {car.get('rarity')}\n" 
        f"{decorations['money_emoji']} Оценка: <b>{format_money(car.get('value',0))}</b>\n" 
        f"⚙️ HP: <b>{car.get('hp',0)}</b> | ACC: <b>{car.get('acc',0)}</b> | HND: <b>{car.get('handling',0)}</b>\n" 
        f"{wear_emoji} Износ: <b>{wear}%</b>\n"
        f"🆔 <code>{car.get('id')}</code>\n"
        f"\nСтраница: {index+1}/{total}"
    ) 
    
    kb = create_garage_keyboard(index, total, car['id'])
    
    try: 
        if car.get('image_path') and os.path.exists(car.get('image_path')): 
            with open(car['image_path'], 'rb') as ph: 
                if edit_message: 
                    try: 
                        await bot.edit_message_media( 
                            media=types.InputMediaPhoto(media=ph, caption=caption, parse_mode='HTML'), 
                            chat_id=edit_message['chat_id'], 
                            message_id=edit_message['message_id'], 
                            reply_markup=kb
                        ) 
                        return 
                    except Exception as e: 
                        print(f"Ошибка редактирования медиа: {e}")
                        await bot.send_photo(chat_id, ph, caption=caption, parse_mode='HTML', reply_markup=kb)
                        try:
                            await bot.delete_message(edit_message['chat_id'], edit_message['message_id'])
                        except:
                            pass
                        return
                else: 
                    if reply_to: 
                        await bot.send_photo(reply_to.chat.id, ph, caption=caption, parse_mode='HTML', reply_markup=kb) 
                    else: 
                        await bot.send_photo(chat_id, ph, caption=caption, parse_mode='HTML', reply_markup=kb) 
                return 
    except Exception as e: 
        print(f"Ошибка отправки фото: {e}")

    text = caption + '\n\n📷 Фотка в разработке..' 
    try: 
        if edit_message: 
            try:
                await bot.edit_message_text( 
                    chat_id=edit_message['chat_id'], 
                    message_id=edit_message['message_id'], 
                    text=text, 
                    parse_mode='HTML', 
                    reply_markup=kb
                ) 
                return
            except Exception as e:
                print(f"Ошибка редактирования текста: {e}")
    except Exception as e: 
        print(f"Ошибка отправки текста: {e}")
        
    if reply_to: 
        await bot.send_message(reply_to.chat.id, text, parse_mode='HTML', reply_markup=kb) 
    else: 
        await bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=kb) 

@dp.message_handler(lambda m: m.text and is_command_message(m, ['гараж', 'garage', 'машины'])) 
async def show_garage(message:types.Message): 
    uid=message.from_user.id 
    ensure_user_initialized(uid) 
    cars_list = user_garage[uid] 
    if not cars_list: 
        decorations = get_event_decorations()
        await message.reply(f'{decorations["garage_emoji"]} <b>Твой гараж пуст</b> — получи первую машину: "машина"', parse_mode='HTML') 
        return 
    
    index = 0 
    car = cars_list[index] 
    
    await send_car_card(message.chat.id, car, index, len(cars_list), reply_to=message) 

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('garage_nav:')) 
async def garage_nav(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    user_id = callback_query.from_user.id 
    try: 
        new_index = int(callback_query.data.split(':',1)[1]) 
    except Exception: 
        return 
    
    cars_list = user_garage.get(user_id, []) 
    if not cars_list: 
        try: 
            decorations = get_event_decorations()
            await bot.edit_message_text(f'{decorations["garage_emoji"]} Твой гараж пуст', 
                                      chat_id=callback_query.message.chat.id, 
                                      message_id=callback_query.message.message_id) 
        except Exception: 
            pass 
        return 

    new_index = new_index % len(cars_list) 
    car = cars_list[new_index] 
    
    await send_car_card(
        callback_query.message.chat.id, 
        car, 
        new_index, 
        len(cars_list), 
        edit_message={
            'chat_id': callback_query.message.chat.id,
            'message_id': callback_query.message.message_id
        }
    )

# ========== СИСТЕМА КАРШЕРИНГА ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['каршеринг', 'carsharing']))
async def carsharing_command(message: types.Message):
    """Управление каршерингом"""
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    # Subscription check for carsharing
    try:
        if not await is_user_subscribed(user_id):
            await message.reply("❌ Каршеринг доступен только подписчикам.")
            return
    except Exception:
        await message.reply("❌ Не удалось проверить подписку. Попробуйте позже.")
        return
    
    cars_list = user_garage.get(user_id, [])
    
    if len(cars_list) < 3:
        await message.reply(
            "🚗 <b>СИСТЕМА КАРШЕРИНГА</b>\n\n"
            "❌ Для использования каршеринга нужно минимум 3 машины в гараже!\n\n"
            "💡 Каршеринг позволяет получать пассивный доход, но машины изнашиваются.",
            parse_mode='HTML'
        )
        return
    
    carsharing_info = user_carsharing.get(user_id, {})
    active_cars = carsharing_info.get('active_cars', [])
    last_collect = carsharing_info.get('last_collect', 0)
    
    # Расчет дохода
    rarity_multipliers = {
        'Обычные': 1.0,
        'Редкие': 1.5,
        'Эпические': 2.5,
        'Легендарные': 4.0,
        'Эксклюзивные': 6.0
    }
    
    current_time = time.time()
    hours_passed = (current_time - last_collect) / 3600 if last_collect > 0 else 0
    total_income = 0
    
    for car_id in active_cars:
        car = next((c for c in cars_list if c.get('id') == car_id), None)
        if car:
            base_income = max(100, car['value'] // 1000)
            rarity = car.get('rarity', 'Обычные')
            multiplier = rarity_multipliers.get(rarity, 1.0)
            income_per_hour = int(base_income * multiplier)
            total_income += int(income_per_hour * hours_passed)
    
    text = (
        "🚗 <b>СИСТЕМА КАРШЕРИНГА</b>\n\n"
        f"💰 Накопленный доход: {format_money(total_income)}\n"
        f"🏎️ Активных машин: {len(active_cars)}/5\n\n"
    )
    
    if active_cars:
        text += "🔧 <b>Активные машины в каршеринге:</b>\n"
        for car_id in active_cars:
            car = next((c for c in cars_list if c.get('id') == car_id), None)
            if car:
                wear_emoji = get_wear_emoji(car.get('wear', 100))
                text += f"• {car['name']} {wear_emoji} ({car.get('wear', 100)}%)\n"
    
    kb = types.InlineKeyboardMarkup()
    
    if total_income > 0:
        kb.add(types.InlineKeyboardButton(
            text=f"💰 Собрать доход ({format_money(total_income)})", 
            callback_data="carsharing_collect"
        ))
    
    kb.row(
        types.InlineKeyboardButton(text="➕ Добавить машину", callback_data="carsharing_add_menu"),
        types.InlineKeyboardButton(text="➖ Убрать машину", callback_data="carsharing_remove_menu")
    )
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "carsharing_add_menu")
async def carsharing_add_menu(callback_query: types.CallbackQuery):
    """Меню добавления машины в каршеринг"""
    user_id = callback_query.from_user.id
    ensure_user_initialized(user_id)
    
    cars_list = user_garage.get(user_id, [])
    carsharing_info = user_carsharing.get(user_id, {})
    active_cars = carsharing_info.get('active_cars', [])
    
    available_cars = [car for car in cars_list if car.get('id') not in active_cars and car.get('sellable', True)]
    
    if not available_cars:
        await bot.answer_callback_query(callback_query.id, "❌ Нет доступных машин для добавления!", show_alert=True)
        return
    
    if len(active_cars) >= 5:
        await bot.answer_callback_query(callback_query.id, "❌ Максимум 5 машин в каршеринге!", show_alert=True)
        return
    
    # Группируем машины по редкости
    cars_by_rarity = {}
    for car in available_cars:
        rarity = car.get('rarity', 'Обычные')
        if rarity not in cars_by_rarity:
            cars_by_rarity[rarity] = []
        cars_by_rarity[rarity].append(car)
    
    # Множители дохода по редкости
    rarity_multipliers = {
        'Обычные': 1.0,
        'Редкие': 1.5,
        'Эпические': 2.5,
        'Легендарные': 4.0,
        'Эксклюзивные': 6.0
    }
    
    text = "🚗 <b>ВЫБЕРИТЕ МАШИНУ ДЛЯ КАРШЕРИНГА</b>\n\n"
    text += "💡 Доход зависит от класса машины:\n"
    text += "• Обычные: x1.0\n"
    text += "• Редкие: x1.5\n"
    text += "• Эпические: x2.5\n"
    text += "• Легендарные: x4.0\n"
    text += "• Эксклюзивные: x6.0\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    # Порядок редкости
    rarity_order = ['Обычные', 'Редкие', 'Эпические', 'Легендарные', 'Эксклюзивные']
    
    for rarity in rarity_order:
        if rarity in cars_by_rarity:
            for car in cars_by_rarity[rarity]:
                base_income = max(100, car['value'] // 1000)
                multiplier = rarity_multipliers.get(rarity, 1.0)
                income_per_hour = int(base_income * multiplier)
                
                rarity_emoji = {
                    'Обычные': '⚪',
                    'Редкие': '🔵',
                    'Эпические': '🟣',
                    'Легендарные': '🟡',
                    'Эксклюзивные': '🔴'
                }.get(rarity, '⚪')
                
                kb.add(types.InlineKeyboardButton(
                    text=f"{rarity_emoji} {car['name']} - {format_money(income_per_hour)}/час",
                    callback_data=f"carsharing_add:{car['id']}"
                ))
    
    kb.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="carsharing_back"))
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML',
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('carsharing_add:'))
async def carsharing_add_car(callback_query: types.CallbackQuery):
    """Добавление машины в каршеринг"""
    user_id = callback_query.from_user.id
    car_id = callback_query.data.split(':', 1)[1]
    
    ensure_user_initialized(user_id)
    
    if user_id not in user_carsharing:
        user_carsharing[user_id] = {'active_cars': [], 'last_collect': time.time()}
    
    if len(user_carsharing[user_id]['active_cars']) >= 5:
        await bot.answer_callback_query(callback_query.id, "❌ Максимум 5 машин в каршеринге!", show_alert=True)
        return
    
    if car_id in user_carsharing[user_id]['active_cars']:
        await bot.answer_callback_query(callback_query.id, "❌ Эта машина уже в каршеринге!", show_alert=True)
        return
    
    user_carsharing[user_id]['active_cars'].append(car_id)
    save_data()
    
    await bot.answer_callback_query(callback_query.id, "✅ Машина добавлена в каршеринг!")
    
    # Правильно устанавливаем from_user
    message = callback_query.message
    message.from_user = callback_query.from_user
    await carsharing_command(message)

@dp.callback_query_handler(lambda c: c.data == "carsharing_remove_menu")
async def carsharing_remove_menu(callback_query: types.CallbackQuery):
    """Меню удаления машины из каршеринга"""
    user_id = callback_query.from_user.id
    ensure_user_initialized(user_id)
    
    carsharing_info = user_carsharing.get(user_id, {})
    active_cars = carsharing_info.get('active_cars', [])
    
    if not active_cars:
        await bot.answer_callback_query(callback_query.id, "❌ Нет машин в каршеринге!", show_alert=True)
        return
    
    cars_list = user_garage.get(user_id, [])
    
    text = "🚗 <b>ВЫБЕРИТЕ МАШИНУ ДЛЯ УДАЛЕНИЯ ИЗ КАРШЕРИНГА</b>\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    for car_id in active_cars:
        car = next((c for c in cars_list if c.get('id') == car_id), None)
        if car:
            kb.add(types.InlineKeyboardButton(
                text=f"{car['name']} ({car.get('wear', 100)}%)",
                callback_data=f"carsharing_remove:{car_id}"
            ))
    
    kb.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="carsharing_back"))
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML',
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('carsharing_remove:'))
async def carsharing_remove_car(callback_query: types.CallbackQuery):
    """Удаление машины из каршеринга"""
    user_id = callback_query.from_user.id
    car_id = callback_query.data.split(':', 1)[1]
    
    ensure_user_initialized(user_id)
    
    if user_id not in user_carsharing or car_id not in user_carsharing[user_id]['active_cars']:
        await bot.answer_callback_query(callback_query.id, "❌ Машина не найдена в каршеринге!", show_alert=True)
        return
    
    user_carsharing[user_id]['active_cars'].remove(car_id)
    save_data()
    
    await bot.answer_callback_query(callback_query.id, "✅ Машина удалена из каршеринга!")
    
    # Правильно устанавливаем from_user
    message = callback_query.message
    message.from_user = callback_query.from_user
    await carsharing_command(message)

@dp.callback_query_handler(lambda c: c.data == "carsharing_collect")
async def carsharing_collect(callback_query: types.CallbackQuery):
    """Сбор дохода с каршеринга"""
    user_id = callback_query.from_user.id
    ensure_user_initialized(user_id)
    
    if user_id not in user_carsharing:
        await bot.answer_callback_query(callback_query.id, "❌ Нет активного каршеринга!", show_alert=True)
        return
    
    carsharing_info = user_carsharing[user_id]
    active_cars = carsharing_info.get('active_cars', [])
    last_collect = carsharing_info.get('last_collect', 0)
    
    if not active_cars:
        await bot.answer_callback_query(callback_query.id, "❌ Нет машин в каршеринге!", show_alert=True)
        return
    
    cars_list = user_garage.get(user_id, [])
    current_time = time.time()
    hours_passed = (current_time - last_collect) / 3600 if last_collect > 0 else 0
    
    if hours_passed < 0.1:  # Минимум 6 минут между сборами
        await bot.answer_callback_query(callback_query.id, "❌ Слишком рано для сбора дохода!", show_alert=True)
        return
    
    # Множители дохода по редкости
    rarity_multipliers = {
        'Обычные': 1.0,
        'Редкие': 1.5,
        'Эпические': 2.5,
        'Легендарные': 4.0,
        'Эксклюзивные': 6.0
    }
    
    total_income = 0
    total_wear = 0
    
    for car_id in active_cars:
        car = next((c for c in cars_list if c.get('id') == car_id), None)
        if car:
            base_income = max(100, car['value'] // 1000)
            rarity = car.get('rarity', 'Обычные')
            multiplier = rarity_multipliers.get(rarity, 1.0)
            income_per_hour = int(base_income * multiplier)
            car_income = int(income_per_hour * hours_passed)
            total_income += car_income
            
            # Износ машины (1% за каждые 10 часов)
            wear_loss = min(5, int(hours_passed / 10))  # Макс 5% износа за сбор
            if 'wear' not in car:
                car['wear'] = 100
            car['wear'] = max(0, car['wear'] - wear_loss)
            total_wear += wear_loss
    
    user_balance[user_id] += total_income
    user_carsharing[user_id]['last_collect'] = current_time
    save_data()
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"💰 <b>ДОХОД СОБРАН!</b>\n\n"
             f"💵 Получено: {format_money(total_income)}\n"
             f"🔧 Общий износ: -{total_wear}%\n"
             f"💳 Баланс: {format_money(user_balance[user_id])}\n\n"
             f"⚠️ Не забывайте чинить машины в тюнинге!",
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data == "carsharing_back")
async def carsharing_back(callback_query: types.CallbackQuery):
    """Назад в меню каршеринга"""
    # Правильно устанавливаем from_user
    message = callback_query.message
    message.from_user = callback_query.from_user
    await carsharing_command(message)

# ========== СИСТЕМА ТАКСОПАРКА ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['такси', 'таксопарк', 'taxi']))
async def taxipark_command(message: types.Message):
    """Управление таксопарком"""
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    # Subscription check for taxipark
    try:
        if not await is_user_subscribed(user_id):
            await message.reply("❌ Таксопарк доступен только подписчикам.")
            return
    except Exception:
        await message.reply("❌ Не удалось проверить подписку. Попробуйте позже.")
        return
    
    taxipark_info = user_taxipark.get(user_id, {})
    has_taxi = taxipark_info.get('has_taxi', False)
    taxi_level = taxipark_info.get('level', 1)  # 1=Обычное, 2=Премиум, 3=VIP
    last_collect = taxipark_info.get('last_collect', 0)
    
    balance = user_balance.get(user_id, 0)
    
    # Уровни такси
    taxi_levels = {
        1: {"name": "🚕 Обычное такси", "income": 30000, "cost": 200000},
        2: {"name": "🚖 Премиум такси", "income": 50000, "cost": 800000},
        3: {"name": "🏎️ VIP такси", "income": 70000, "cost": 3000000}
    }
    
    text = "🚕 <b>СИСТЕМА ТАКСОПАРКА</b>\n\n"
    
    if not has_taxi:
        text += (
            "💡 Таксопарк - это стабильный источник дохода!\n\n"
            "📊 <b>Доступные уровни:</b>\n"
            "🚕 Обычное такси: 30,000$/час (200,000$)\n"
            "🚖 Премиум такси: 50,000$/час (800,000$)\n"
            "🏎️ VIP такси: 70,000$/час (3,000,000$)\n\n"
            f"💰 Ваш баланс: {format_money(balance)}\n"
        )
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        
        # Кнопки для покупки
        for level, info in taxi_levels.items():
            if balance >= info['cost']:
                kb.add(types.InlineKeyboardButton(
                    text=f"✅ {info['name']} - {format_money(info['cost'])}",
                    callback_data=f"taxi_buy:{level}"
                ))
            else:
                kb.add(types.InlineKeyboardButton(
                    text=f"❌ {info['name']} - {format_money(info['cost'])}",
                    callback_data="taxi_cant_buy"
                ))
            
    else:
        # Расчет дохода
        current_level_info = taxi_levels[taxi_level]
        current_time = time.time()
        hours_passed = (current_time - last_collect) / 3600 if last_collect > 0 else 0
        income = int(current_level_info['income'] * hours_passed)
        
        text += (
            f"✅ <b>Текущий уровень: {current_level_info['name']}</b>\n"
            f"💰 Накопленный доход: {format_money(income)}\n"
            f"⏰ Часов прошло: {hours_passed:.1f}\n"
            f"💵 Доход: {format_money(current_level_info['income'])}/час\n\n"
        )
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        
        if income > 0:
            kb.add(types.InlineKeyboardButton(
                text=f"💰 Собрать доход ({format_money(income)})", 
                callback_data="taxi_collect"
            ))
        
        # Кнопка улучшения, если не максимальный уровень
        if taxi_level < 3:
            next_level = taxi_level + 1
            next_level_info = taxi_levels[next_level]
            upgrade_cost = next_level_info['cost'] - current_level_info['cost']
            
            text += f"📈 <b>Доступно улучшение:</b>\n"
            text += f"{next_level_info['name']} - {format_money(next_level_info['income'])}/час\n"
            text += f"💵 Стоимость улучшения: {format_money(upgrade_cost)}\n"
            
            if balance >= upgrade_cost:
                kb.add(types.InlineKeyboardButton(
                    text=f"⬆️ Улучшить до {next_level_info['name']}",
                    callback_data=f"taxi_upgrade:{next_level}"
                ))
            else:
                kb.add(types.InlineKeyboardButton(
                    text=f"❌ Недостаточно средств для улучшения",
                    callback_data="taxi_cant_buy"
                ))
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("taxi_buy"))
async def taxi_buy(callback_query: types.CallbackQuery):
    """Покупка таксопарка"""
    user_id = callback_query.from_user.id
    
    # Определяем уровень такси из callback
    parts = callback_query.data.split(':')
    level = int(parts[1]) if len(parts) > 1 else 1
    
    taxi_levels = {
        1: {"name": "🚕 Обычное такси", "income": 30000, "cost": 200000},
        2: {"name": "🚖 Премиум такси", "income": 50000, "cost": 800000},
        3: {"name": "🏎️ VIP такси", "income": 70000, "cost": 3000000}
    }
    
    level_info = taxi_levels[level]
    
    if user_balance.get(user_id, 0) < level_info['cost']:
        await bot.answer_callback_query(callback_query.id, "❌ Недостаточно средств!", show_alert=True)
        return
    
    user_balance[user_id] -= level_info['cost']
    user_taxipark[user_id] = {
        'has_taxi': True,
        'level': level,
        'last_collect': time.time()
    }
    save_data()
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"🎉 <b>ТАКСОПАРК КУПЛЕН!</b>\n\n"
             f"{level_info['name']} приобретено!\n"
             f"💰 Доход: {format_money(level_info['income'])}/час\n"
             f"💡 Возвращайтесь для сбора дохода!\n\n"
             f"💳 Баланс: {format_money(user_balance[user_id])}",
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("taxi_upgrade:"))
async def taxi_upgrade(callback_query: types.CallbackQuery):
    """Улучшение таксопарка"""
    user_id = callback_query.from_user.id
    
    new_level = int(callback_query.data.split(':')[1])
    
    taxi_levels = {
        1: {"name": "🚕 Обычное такси", "income": 30000, "cost": 200000},
        2: {"name": "🚖 Премиум такси", "income": 50000, "cost": 800000},
        3: {"name": "🏎️ VIP такси", "income": 70000, "cost": 3000000}
    }
    
    current_level = user_taxipark[user_id].get('level', 1)
    current_info = taxi_levels[current_level]
    new_info = taxi_levels[new_level]
    upgrade_cost = new_info['cost'] - current_info['cost']
    
    if user_balance.get(user_id, 0) < upgrade_cost:
        await bot.answer_callback_query(callback_query.id, "❌ Недостаточно средств!", show_alert=True)
        return
    
    user_balance[user_id] -= upgrade_cost
    user_taxipark[user_id]['level'] = new_level
    save_data()
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"⬆️ <b>ТАКСОПАРК УЛУЧШЕН!</b>\n\n"
             f"Новый уровень: {new_info['name']}\n"
             f"💰 Новый доход: {format_money(new_info['income'])}/час\n"
             f"💵 Потрачено: {format_money(upgrade_cost)}\n"
             f"💳 Баланс: {format_money(user_balance[user_id])}",
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data == "taxi_collect")
async def taxi_collect(callback_query: types.CallbackQuery):
    """Сбор дохода с таксопарка"""
    user_id = callback_query.from_user.id
    
    if user_id not in user_taxipark or not user_taxipark[user_id].get('has_taxi', False):
        await bot.answer_callback_query(callback_query.id, "❌ У вас нет таксопарка!", show_alert=True)
        return
    
    taxipark_info = user_taxipark[user_id]
    taxi_level = taxipark_info.get('level', 1)
    last_collect = taxipark_info.get('last_collect', 0)
    current_time = time.time()
    hours_passed = (current_time - last_collect) / 3600
    
    if hours_passed < 0.1:  # Минимум 6 минут между сборами
        await bot.answer_callback_query(callback_query.id, "❌ Слишком рано для сбора дохода!", show_alert=True)
        return
    
    taxi_levels = {
        1: {"name": "🚕 Обычное такси", "income": 30000},
        2: {"name": "🚖 Премиум такси", "income": 50000},
        3: {"name": "🏎️ VIP такси", "income": 70000}
    }
    
    income_per_hour = taxi_levels[taxi_level]['income']
    income = int(income_per_hour * hours_passed)
    user_balance[user_id] += income
    user_taxipark[user_id]['last_collect'] = current_time
    save_data()
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"💰 <b>ДОХОД СОБРАН!</b>\n\n"
             f"💵 Получено: {format_money(income)}\n"
             f"⏰ Часов работы: {hours_passed:.1f}\n"
             f"💳 Баланс: {format_money(user_balance[user_id])}\n\n"
             f"{taxi_levels[taxi_level]['name']} продолжает работать!",
        parse_mode='HTML'
    )

# ========== СИСТЕМА БАРАХОЛКИ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['барахолка', 'вторичный', 'flea market', 'flea', 'market']))
async def flea_market_command(message: types.Message):
    """Просмотр барахолки"""
    if not flea_market:
        await message.reply(
            "🏪 <b>БАРАХОЛКА</b>\n\n"
            "❌ В данный момент на барахолке нет предложений.\n\n"
            "💡 Вы можете выставить свою машину на продажу через гараж!"
        )
        return
    
    text = "🏪 <b>БАРАХОЛКА - ВТОРИЧНЫЙ РЫНОК</b>\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    for i, (offer_id, offer) in enumerate(list(flea_market.items())[:10], 1):  # Показываем первые 10 предложений
        seller_id = offer['seller_id']
        car = offer['car']
        price = offer['price']
        
        try:
            seller = await bot.get_chat(seller_id)
            seller_name = f"@{seller.username}" if seller.username else f"ID {seller_id}"
        except:
            seller_name = f"ID {seller_id}"
        
        wear_emoji = get_wear_emoji(car.get('wear', 100))
        
        rarity_emoji = {
            'Обычные': '⚪',
            'Редкие': '🔵',
            'Эпические': '🟣',
            'Легендарные': '🟡',
            'Эксклюзивные': '🔴'
        }.get(car.get('rarity', 'Обычные'), '⚪')
        
        text += (
            f"{i}. {rarity_emoji} <b>{car['name']}</b>\n"
            f"   💵 Цена: {format_money(price)}\n"
            f"   {wear_emoji} Износ: {car.get('wear', 100)}%\n"
            f"   👤 {seller_name}\n\n"
        )
        
        # Добавляем кнопку покупки
        kb.add(types.InlineKeyboardButton(
            text=f"💰 {i}. {car['name']} - {format_money(price)}",
            callback_data=f"flea_buy:{offer_id}"
        ))
    
    text += "💡 Нажмите на кнопку, чтобы купить машину"
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('flea_add:'))
async def flea_add_car(callback_query: types.CallbackQuery):
    """Добавление машины на барахолку"""
    user_id = callback_query.from_user.id
    car_id = callback_query.data.split(':', 1)[1]
    
    ensure_user_initialized(user_id)
    
    cars_list = user_garage.get(user_id, [])
    car = next((c for c in cars_list if c.get('id') == car_id), None)
    
    if not car:
        await bot.answer_callback_query(callback_query.id, "❌ Машина не найдена!", show_alert=True)
        return
    
    if not car.get('sellable', True):
        await bot.answer_callback_query(callback_query.id, "❌ Эту машину нельзя продать!", show_alert=True)
        return
    
    # Проверяем, не выставлена ли уже машина
    for offer_id, offer in flea_market.items():
        if offer['car']['id'] == car_id:
            await bot.answer_callback_query(callback_query.id, "❌ Эта машина уже на барахолке!", show_alert=True)
            return
    
    text = (
        f"🏪 <b>ВЫСТАВИТЬ НА БАРАХОЛКУ</b>\n\n"
        f"🚗 Машина: <b>{car['name']}</b>\n"
        f"💎 Редкость: <b>{car['rarity']}</b>\n"
        f"💵 Текущая стоимость: <b>{format_money(car['value'])}</b>\n\n"
        f"💡 Введите цену продажи (не менее {format_money(max(1000, car['value'] // 2))}):"
    )
    
    await bot.send_message(
        user_id,
        text,
        parse_mode='HTML'
    )
    
    # Сохраняем временные данные для ожидания цены
    flea_pending[user_id] = car_id
    await bot.answer_callback_query(callback_query.id)

@dp.message_handler(lambda m: m.text and m.text.isdigit() and m.from_user.id in flea_pending)
async def flea_set_price(message: types.Message):
    """Установка цены для барахолки"""
    user_id = message.from_user.id
    car_id = flea_pending.get(user_id)
    
    if not car_id:
        return
    
    del flea_pending[user_id]
    
    cars_list = user_garage.get(user_id, [])
    car = next((c for c in cars_list if c.get('id') == car_id), None)
    
    if not car:
        await message.reply("❌ Машина не найдена!")
        return
    
    price = int(message.text)
    min_price = max(1000, car['value'] // 2)
    
    if price < min_price:
        await message.reply(f"❌ Цена слишком низкая! Минимум: {format_money(min_price)}")
        return
    
    # Создаем предложение
    offer_id = generate_unique_id()
    flea_market[offer_id] = {
        'seller_id': user_id,
        'car': car,
        'price': price,
        'created_at': time.time()
    }
    
    await message.reply(
        f"✅ <b>МАШИНА ВЫСТАВЛЕНА НА БАРАХОЛКУ!</b>\n\n"
        f"🚗 {car['name']} ({car['rarity']})\n"
        f"💵 Цена: {format_money(price)}\n"
        f"🆔 ID предложения: <code>{offer_id}</code>\n\n"
        f"💡 Другие игроки могут купить её командой: <code>купить {offer_id}</code>",
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('flea_buy:'))
async def flea_buy_car_callback(callback_query: types.CallbackQuery):
    """Покупка машины с барахолки через кнопку"""
    user_id = callback_query.from_user.id
    ensure_user_initialized(user_id)
    
    offer_id = callback_query.data.split(':', 1)[1]
    
    if offer_id not in flea_market:
        await bot.answer_callback_query(callback_query.id, "❌ Предложение уже продано!", show_alert=True)
        return
    
    offer = flea_market[offer_id]
    
    if offer['seller_id'] == user_id:
        await bot.answer_callback_query(callback_query.id, "❌ Нельзя купить свою же машину!", show_alert=True)
        return
    
    if user_balance.get(user_id, 0) < offer['price']:
        await bot.answer_callback_query(callback_query.id, f"❌ Недостаточно средств! Нужно: {format_money(offer['price'])}", show_alert=True)
        return
    
    # Совершаем сделку
    user_balance[user_id] -= offer['price']
    user_balance[offer['seller_id']] += offer['price']
    
    # Передаем машину новому владельцу
    car = offer['car']
    car_owner_map[car['id']] = user_id
    user_garage[user_id].append(car)
    
    # Удаляем машину у продавца
    seller_garage = user_garage.get(offer['seller_id'], [])
    user_garage[offer['seller_id']] = [c for c in seller_garage if c.get('id') != car['id']]
    
    # Удаляем предложение
    del flea_market[offer_id]
    
    save_data()
    
    # Уведомляем покупателя
    await bot.send_message(
        user_id,
        f"✅ <b>МАШИНА КУПЛЕНА!</b>\n\n"
        f"🚗 {car['name']} ({car['rarity']})\n"
        f"💵 Цена: {format_money(offer['price'])}\n"
        f"💳 Баланс: {format_money(user_balance[user_id])}\n\n"
        f"🎉 Машина добавлена в ваш гараж!",
        parse_mode='HTML'
    )
    
    # Уведомляем продавца
    try:
        await bot.send_message(
            offer['seller_id'],
            f"💰 <b>МАШИНА ПРОДАНА!</b>\n\n"
            f"🚗 {car['name']}\n"
            f"💵 Получено: {format_money(offer['price'])}\n"
            f"💳 Баланс: {format_money(user_balance[offer['seller_id']])}",
            parse_mode='HTML'
        )
    except:
        pass
    
    await bot.answer_callback_query(callback_query.id, "✅ Машина куплена!")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('купить '))
async def flea_buy_car(message: types.Message):
    """Покупка машины с барахолки"""
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            await message.reply("❌ Использование: купить [ID_предложения]")
            return
        
        offer_id = parts[1]
        
        if offer_id not in flea_market:
            await message.reply("❌ Предложение не найдено!")
            return
        
        offer = flea_market[offer_id]
        
        if offer['seller_id'] == user_id:
            await message.reply("❌ Нельзя купить свою же машину!")
            return
        
        if user_balance.get(user_id, 0) < offer['price']:
            await message.reply(f"❌ Недостаточно средств! Нужно: {format_money(offer['price'])}")
            return
        
        # Совершаем сделку
        user_balance[user_id] -= offer['price']
        user_balance[offer['seller_id']] += offer['price']
        
        # Передаем машину новому владельцу
        car = offer['car']
        car_owner_map[car['id']] = user_id
        user_garage[user_id].append(car)
        
        # Удаляем машину у продавца
        seller_garage = user_garage.get(offer['seller_id'], [])
        user_garage[offer['seller_id']] = [c for c in seller_garage if c.get('id') != car['id']]
        
        # Удаляем предложение
        del flea_market[offer_id]
        
        save_data()
        
        # Уведомляем продавца
        try:
            await bot.send_message(
                offer['seller_id'],
                f"💰 <b>ВАША МАШИНА ПРОДАНА!</b>\n\n"
                f"🚗 {car['name']} ({car['rarity']})\n"
                f"💵 Получено: {format_money(offer['price'])}\n"
                f"👤 Покупатель: ID {user_id}\n"
                f"💳 Ваш баланс: {format_money(user_balance[offer['seller_id']])}",
                parse_mode='HTML'
            )
        except:
            pass
        
        await message.reply(
            f"🎉 <b>ПОКУПКА УСПЕШНА!</b>\n\n"
            f"🚗 Вы купили: <b>{car['name']}</b>\n"
            f"💎 Редкость: <b>{car['rarity']}</b>\n"
            f"💵 Цена: <b>{format_money(offer['price'])}</b>\n"
            f"💳 Ваш баланс: <b>{format_money(user_balance[user_id])}</b>\n\n"
            f"✅ Машина добавлена в ваш гараж!",
            parse_mode='HTML'
        )
        
    except Exception as e:
        await message.reply("❌ Ошибка при покупке!")

# ========== УЛУЧШЕННЫЙ ТЮНИНГ С РЕМОНТОМ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['тюнинг', 'улучшить', 'tune'])) 
async def tune_cmd(message: types.Message): 
    uid = message.from_user.id 
    ensure_user_initialized(uid) 
    cars_list = user_garage.get(uid, []) 
    if not cars_list: 
        await message.reply('❌ У тебя нет машин для тюнинга.') 
        return 
    
    kb = types.InlineKeyboardMarkup(row_width=1) 
    for c in cars_list: 
        wear_emoji = get_wear_emoji(c.get('wear', 100))
        kb.add(types.InlineKeyboardButton(
            text=f"{wear_emoji} {c['name']} (ID {c['id'][:6]}...) - {c.get('wear', 100)}%", 
            callback_data=f'tune_select:{c["id"]}'
        )) 
    
    await message.reply('🔧 <b>ВЫБЕРИТЕ МАШИНУ ДЛЯ ТЮНИНГА</b>', parse_mode='HTML', reply_markup=kb) 

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tune_select:')) 
async def tune_select(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    car_id = callback_query.data.split(':',1)[1] 
    uid = callback_query.from_user.id 
    car = next((c for c in user_garage.get(uid, []) if c.get('id')==car_id), None) 
    if not car: 
        await bot.answer_callback_query(callback_query.id, '❌ Машина не найдена.', show_alert=True) 
        return 
    
    wear = car.get('wear', 100)
    wear_emoji = get_wear_emoji(wear)
    
    price_hp = max(30000, int(car.get('value',10000) * 0.05)) 
    price_acc = max(30000, int(car.get('value',10000) * 0.04)) 
    price_hand = max(30000, int(car.get('value',10000) * 0.04)) 
    price_repair = max(30000, int(car.get('value',10000) * (100 - wear) / 500)) 
    
    kb = types.InlineKeyboardMarkup(row_width=1) 
    kb.add(types.InlineKeyboardButton(text=f"💪 +10% HP — {price_hp:,}$", callback_data=f'tune_buy:{car_id}:hp:{price_hp}')) 
    kb.add(types.InlineKeyboardButton(text=f"⚡ +10% ACC — {price_acc:,}$", callback_data=f'tune_buy:{car_id}:acc:{price_acc}')) 
    kb.add(types.InlineKeyboardButton(text=f"🎯 +10% HND — {price_hand:,}$", callback_data=f'tune_buy:{car_id}:handling:{price_hand}')) 
    
    if wear < 100:
        kb.add(types.InlineKeyboardButton(text=f"🔧 Ремонт до 100% — {price_repair:,}$", callback_data=f'tune_repair:{car_id}:{price_repair}')) 
    
    text = (
        f"🔧 <b>ТЮНИНГ МАШИНЫ</b>\n\n"
        f"🚗 <b>{car['name']}</b>\n"
        f"💪 Характеристики: HP {car['hp']} | ACC {car['acc']} | HND {car['handling']}\n"
        f"{wear_emoji} Износ: {wear}%\n"
        f"💵 Стоимость: {format_money(car['value'])}"
    )
    
    await bot.send_message(uid, text, parse_mode='HTML', reply_markup=kb) 

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tune_repair:')) 
async def tune_repair(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    parts = callback_query.data.split(':') 
    if len(parts) != 3: 
        return 
    
    car_id = parts[1] 
    try: 
        price = int(parts[2]) 
    except Exception: 
        await bot.answer_callback_query(callback_query.id, '❌ Ошибка данных.', show_alert=True) 
        return 
    
    uid = callback_query.from_user.id 
    ensure_user_initialized(uid) 
    
    if user_balance.get(uid,0) < price: 
        await bot.answer_callback_query(callback_query.id, '❌ Недостаточно средств.', show_alert=True) 
        return 
    
    car = next((c for c in user_garage.get(uid, []) if c.get('id')==car_id), None) 
    if not car: 
        await bot.answer_callback_query(callback_query.id, '❌ Машина не найдена.', show_alert=True) 
        return 
    
    # Ремонтируем машину
    user_balance[uid] -= price 
    car['wear'] = 100
    
    update_quest_progress(uid, 'car_tuned', 1)
    
    save_data() 
    
    await bot.send_message(
        uid, 
        f"✅ <b>МАШИНА ОТРЕМОНТИРОВАНА!</b>\n\n"
        f"🚗 {car['name']} — износ восстановлен до 100%\n"
        f"💵 Стоимость ремонта: {format_money(price)}\n"
        f"💳 Баланс: {format_money(user_balance[uid])}",
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tune_buy:')) 
async def tune_buy(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    parts = callback_query.data.split(':') 
    if len(parts) != 4: 
        return 
    
    car_id = parts[1] 
    stat = parts[2] 
    try: 
        price = int(parts[3]) 
    except Exception: 
        await bot.answer_callback_query(callback_query.id, '❌ Ошибка данных.', show_alert=True) 
        return 
    
    uid = callback_query.from_user.id 
    ensure_user_initialized(uid) 
    
    if user_balance.get(uid,0) < price: 
        await bot.answer_callback_query(callback_query.id, '❌ Недостаточно средств.', show_alert=True) 
        return 
    
    car = next((c for c in user_garage.get(uid, []) if c.get('id')==car_id), None) 
    if not car: 
        await bot.answer_callback_query(callback_query.id, '❌ Машина не найдена.', show_alert=True) 
        return 
    
    increment = max(1, int(car.get(stat,0) * 0.1)) 
    car[stat] = car.get(stat,0) + increment 
    user_balance[uid] -= price 
    
    update_quest_progress(uid, 'car_tuned', 1)
    
    save_data() 
    
    await bot.send_message(
        uid, 
        f"✅ <b>ТЮНИНГ ПРИМЕНЁН!</b>\n\n"
        f"🚗 {car['name']} — +{increment} {stat.upper()}\n"
        f"💪 Новые характеристики: HP {car['hp']} | ACC {car['acc']} | HND {car['handling']}\n"
        f"💵 Стоимость: {format_money(price)}\n"
        f"💳 Баланс: {format_money(user_balance[uid])}",
        parse_mode='HTML'
    )

# ========== УЛУЧШЕННЫЙ ОБМЕН ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['обмен', 'trade', 'обменяться']))
async def trade_command(message: types.Message):
    """Улучшенная система обмена"""
    user_id = message.from_user.id
    
    if message.reply_to_message:
        # Обмен с конкретным пользователем
        target_user_id = message.reply_to_message.from_user.id
        target_username = message.reply_to_message.from_user.first_name
        
        if target_user_id == user_id:
            await message.reply("❌ Нельзя обмениваться с самим собой!")
            return
            
        ensure_user_initialized(target_user_id)
        
        # Создаем предложение обмена
        trade_id = generate_unique_id()
        trade_offers[trade_id] = {
            'user1_id': user_id,
            'user2_id': target_user_id,
            'user1_car': None,
            'user2_car': None,
            'created_at': time.time()
        }
        
        # Просим первого пользователя выбрать машину
        await message.reply(
            f"🔄 <b>НАЧАЛО ОБМЕНА С {target_username}</b>\n\n"
            f"💡 Выберите машину для обмена:",
            parse_mode='HTML'
        )
        await show_trade_cars(message, trade_id, user_id, 1)
        
        # Уведомляем второго пользователя
        try:
            await bot.send_message(
                target_user_id,
                f"🔄 <b>ПРЕДЛОЖЕНИЕ ОБМЕНА</b>\n\n"
                f"👤 Пользователь {message.from_user.first_name} предложил вам обмен!\n"
                f"💡 Ожидайте, пока он выберет машину...",
                parse_mode='HTML'
            )
        except:
            await message.reply("❌ Не удалось отправить уведомление пользователю. Возможно, он не начинал диалог с ботом.")
        
    else:
        # Обычный обмен
        user_id = message.from_user.id
        ensure_user_initialized(user_id)
        
        cars_list = user_garage.get(user_id, [])
        if len(cars_list) < 2:
            await message.reply("❌ Для обмена нужно как минимум 2 машины в гараже!")
            return
        
        text = (
            "🔄 <b>СИСТЕМА ОБМЕНА МАШИН</b>\n\n"
            "Вы можете обменять одну из своих машин на случайную машину другого игрока.\n"
            "При обмене вы получаете машину случайной редкости!\n\n"
            "💡 <i>Выберите машину для обмена:</i>"
        )
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        for car in cars_list:
            if car.get('sellable', True):
                wear_emoji = get_wear_emoji(car.get('wear', 100))
                kb.add(types.InlineKeyboardButton(
                    text=f"{wear_emoji} {car['name']} ({car['rarity']}) - {car.get('wear', 100)}%",
                    callback_data=f'trade_car:{car["id"]}'
                ))
        
        kb.add(types.InlineKeyboardButton(text='❌ Отмена', callback_data='trade_cancel'))
        
        await message.reply(text, parse_mode='HTML', reply_markup=kb)

async def show_trade_cars(message: types.Message, trade_id: str, user_id: int, user_num: int):
    """Показывает машины для выбора в обмене"""
    cars_list = user_garage.get(user_id, [])
    
    text = f"🔄 <b>ВЫБЕРИТЕ МАШИНУ ДЛЯ ОБМЕНА</b>\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    for car in cars_list:
        if car.get('sellable', True):
            wear_emoji = get_wear_emoji(car.get('wear', 100))
            kb.add(types.InlineKeyboardButton(
                text=f"{wear_emoji} {car['name']} ({car['rarity']}) - {car.get('wear', 100)}%",
                callback_data=f'trade_select:{trade_id}:{user_num}:{car["id"]}'
            ))
    
    kb.add(types.InlineKeyboardButton(text='❌ Отмена', callback_data=f'trade_cancel_id:{trade_id}'))
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('trade_select:'))
async def trade_select_car(callback_query: types.CallbackQuery):
    """Обработка выбора машины для обмена"""
    await bot.answer_callback_query(callback_query.id)
    parts = callback_query.data.split(':')
    trade_id = parts[1]
    user_num = int(parts[2])
    car_id = parts[3]
    
    if trade_id not in trade_offers:
        await bot.send_message(callback_query.from_user.id, "❌ Предложение обмена устарело!")
        return
    
    trade = trade_offers[trade_id]
    user_id = callback_query.from_user.id
    
    # Проверяем, что это правильный пользователь
    if (user_num == 1 and user_id != trade['user1_id']) or (user_num == 2 and user_id != trade['user2_id']):
        await bot.send_message(user_id, "❌ Это не ваш ход!")
        return
    
    # Находим машину
    cars_list = user_garage.get(user_id, [])
    selected_car = next((c for c in cars_list if c.get('id') == car_id), None)
    
    if not selected_car:
        await bot.send_message(user_id, "❌ Машина не найдена!")
        return
    
    # Сохраняем выбор
    if user_num == 1:
        trade['user1_car'] = selected_car
        # Просим второго пользователя выбрать машину
        await bot.send_message(
            trade['user2_id'],
            f"🔄 <b>ВАШ ХОД В ОБМЕНЕ</b>\n\n"
            f"👤 {callback_query.from_user.first_name} выбрал машину для обмена.\n"
            f"💡 Теперь выберите свою машину:",
            parse_mode='HTML'
        )
        await show_trade_cars(callback_query.message, trade_id, trade['user2_id'], 2)
        
        await bot.send_message(
            user_id,
            "✅ <b>МАШИНА ВЫБРАНА!</b>\n\n"
            "⏳ Ожидайте, пока второй участник выберет машину...",
            parse_mode='HTML'
        )
        
    else:
        trade['user2_car'] = selected_car
        # Оба выбрали машины - завершаем обмен
        await complete_trade(trade_id)

async def complete_trade(trade_id: str):
    """Завершение обмена"""
    if trade_id not in trade_offers:
        return
    
    trade = trade_offers[trade_id]
    user1_id = trade['user1_id']
    user2_id = trade['user2_id']
    car1 = trade['user1_car']
    car2 = trade['user2_car']
    
    if not car1 or not car2:
        return
    
    # Удаляем машины у текущих владельцев
    user_garage[user1_id] = [c for c in user_garage[user1_id] if c.get('id') != car1['id']]
    user_garage[user2_id] = [c for c in user_garage[user2_id] if c.get('id') != car2['id']]
    
    # Меняем владельцев
    car_owner_map[car1['id']] = user2_id
    car_owner_map[car2['id']] = user1_id
    
    # Добавляем машины новым владельцам
    user_garage[user1_id].append(car2)
    user_garage[user2_id].append(car1)
    
    save_data()
    
    # Уведомляем участников
    try:
        user1 = await bot.get_chat(user1_id)
        user2 = await bot.get_chat(user2_id)
        
        await bot.send_message(
            user1_id,
            f"✅ <b>ОБМЕН ЗАВЕРШЁН!</b>\n\n"
            f"📤 Вы отдали: <b>{car1['name']}</b>\n"
            f"📥 Получили: <b>{car2['name']}</b>\n"
            f"👤 От: <b>{user2.first_name}</b>\n\n"
            f"🎉 Удачного обмена!",
            parse_mode='HTML'
        )
        
        await bot.send_message(
            user2_id,
            f"✅ <b>ОБМЕН ЗАВЕРШЁН!</b>\n\n"
            f"📤 Вы отдали: <b>{car2['name']}</b>\n"
            f"📥 Получили: <b>{car1['name']}</b>\n"
            f"👤 От: <b>{user1.first_name}</b>\n\n"
            f"🎉 Удачного обмена!",
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка уведомления об обмене: {e}")
    
    # Удаляем предложение обмена
    del trade_offers[trade_id]

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('trade_cancel_id:'))
async def trade_cancel_id(callback_query: types.CallbackQuery):
    """Отмена конкретного обмена"""
    trade_id = callback_query.data.split(':', 1)[1]
    
    if trade_id in trade_offers:
        trade = trade_offers[trade_id]
        # Уведомляем второго участника
        try:
            await bot.send_message(
                trade['user2_id'] if trade['user1_id'] == callback_query.from_user.id else trade['user1_id'],
                "❌ Обмен был отменен вторым участником."
            )
        except:
            pass
        
        del trade_offers[trade_id]
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="❌ Обмен отменен.",
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('trade_car:')) 
async def process_trade(callback_query: types.CallbackQuery): 
    user_id = callback_query.from_user.id 
    car_id = callback_query.data.split(':',1)[1] 
    
    cars_list = user_garage.get(user_id, []) 
    trade_car = None 
    for i, car in enumerate(cars_list): 
        if car.get('id') == car_id: 
            trade_car = cars_list.pop(i) 
            break 
    
    if not trade_car: 
        await bot.answer_callback_query(callback_query.id, "❌ Машина не найдена!", show_alert=True) 
        return 
    
    new_car = await get_random_car_for_free(user_id) 
    user_garage[user_id].append(new_car) 
    
    if trade_car['id'] in car_owner_map: 
        del car_owner_map[trade_car['id']] 
    
    save_data() 
    
    text = (
        f"🔄 <b>ОБМЕН ЗАВЕРШЁН!</b>\n\n"
        f"📤 Вы отдали: <b>{trade_car['name']}</b> ({trade_car['rarity']})\n"
        f"📥 Получили: <b>{new_car['name']}</b> ({new_car['rarity']})\n\n"
        f"💪 Новые характеристики:\n"
        f"HP: {new_car['hp']} | ACC: {new_car['acc']} | HND: {new_car['handling']}\n\n"
        f"🎉 Удачного обмена!"
    )
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data == 'trade_cancel')
async def cancel_trade(callback_query: types.CallbackQuery):
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="❌ Обмен отменён.",
        parse_mode='HTML'
    )

# ========== СИСТЕМА ПАССИВНОГО ДОХОДА ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['доход', 'income', 'пассив']))
async def income_command(message: types.Message):
    """Общая команда для просмотра пассивного дохода"""
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    
    text = "💰 <b>СИСТЕМА ПАССИВНОГО ДОХОДА</b>\n\n"
    
    # Доход с каршеринга
    carsharing_info = user_carsharing.get(user_id, {})
    active_cars = carsharing_info.get('active_cars', [])
    last_collect_cs = carsharing_info.get('last_collect', 0)
    
    current_time = time.time()
    hours_passed_cs = (current_time - last_collect_cs) / 3600 if last_collect_cs > 0 else 0
    carsharing_income = 0
    
    cars_list = user_garage.get(user_id, [])
    for car_id in active_cars:
        car = next((c for c in cars_list if c.get('id') == car_id), None)
        if car:
            income_per_hour = max(100, car['value'] // 1000)
            carsharing_income += int(income_per_hour * hours_passed_cs)
    
    # Доход с таксопарка
    taxipark_info = user_taxipark.get(user_id, {})
    has_taxi = taxipark_info.get('has_taxi', False)
    last_collect_taxi = taxipark_info.get('last_collect', 0)
    
    hours_passed_taxi = (current_time - last_collect_taxi) / 3600 if last_collect_taxi > 0 else 0
    taxipark_income = int(5000 * hours_passed_taxi) if has_taxi else 0
    
    # Общий доход
    total_income = carsharing_income + taxipark_income
    
    # Каршеринг
    text += "🚗 <b>КАРШЕРИНГ</b>\n"
    if active_cars:
        text += f"✅ Активен ({len(active_cars)}/5 машин)\n"
        text += f"💰 Накоплено: {format_money(carsharing_income)}\n"
    else:
        text += "❌ Не активен\n"
        text += "💡 Нужно 3+ машин в гараже\n"
    text += "\n"
    
    # Таксопарк
    text += "🚕 <b>ТАКСОПАРК</b>\n"
    if has_taxi:
        text += f"✅ Активен\n"
        text += f"💰 Накоплено: {format_money(taxipark_income)}\n"
    else:
        text += "❌ Не активен\n"
        text += f"💡 Стоимость: 200,000$\n"
    text += "\n"
    
    text += f"💵 <b>ОБЩИЙ ДОХОД: {format_money(total_income)}</b>\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    if total_income > 0:
        kb.add(types.InlineKeyboardButton(
            text=f"💰 Собрать всё ({format_money(total_income)})", 
            callback_data="income_collect_all"
        ))
    
    kb.row(
        types.InlineKeyboardButton(text="🚗 Каршеринг", callback_data="carsharing_command"),
        types.InlineKeyboardButton(text="🚕 Таксопарк", callback_data="taxipark_command")
    )
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "income_collect_all")
async def income_collect_all(callback_query: types.CallbackQuery):
    """Сбор всего пассивного дохода"""
    user_id = callback_query.from_user.id
    ensure_user_initialized(user_id)
    
    total_income = 0
    current_time = time.time()
    
    # Сбор дохода с каршеринга
    if user_id in user_carsharing:
        carsharing_info = user_carsharing[user_id]
        active_cars = carsharing_info.get('active_cars', [])
        last_collect_cs = carsharing_info.get('last_collect', 0)
        
        hours_passed_cs = (current_time - last_collect_cs) / 3600 if last_collect_cs > 0 else 0
        
        if hours_passed_cs >= 0.1 and active_cars:  # Минимум 6 минут
            cars_list = user_garage.get(user_id, [])
            total_wear = 0
            
            for car_id in active_cars:
                car = next((c for c in cars_list if c.get('id') == car_id), None)
                if car:
                    income_per_hour = max(100, car['value'] // 1000)
                    car_income = int(income_per_hour * hours_passed_cs)
                    total_income += car_income
                    
                    # Износ машины
                    wear_loss = min(5, int(hours_passed_cs / 10))
                    if 'wear' not in car:
                        car['wear'] = 100
                    car['wear'] = max(0, car['wear'] - wear_loss)
                    total_wear += wear_loss
            
            user_carsharing[user_id]['last_collect'] = current_time
    
    # Сбор дохода с таксопарка
    if user_id in user_taxipark and user_taxipark[user_id].get('has_taxi', False):
        taxipark_info = user_taxipark[user_id]
        last_collect_taxi = taxipark_info.get('last_collect', 0)
        
        hours_passed_taxi = (current_time - last_collect_taxi) / 3600
        
        if hours_passed_taxi >= 0.1:  # Минимум 6 минут
            taxipark_income = int(5000 * hours_passed_taxi)
            total_income += taxipark_income
            user_taxipark[user_id]['last_collect'] = current_time
    
    if total_income > 0:
        user_balance[user_id] += total_income
        save_data()
        
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"💰 <b>ВЕСЬ ДОХОД СОБРАН!</b>\n\n"
                 f"💵 Получено: {format_money(total_income)}\n"
                 f"💳 Баланс: {format_money(user_balance[user_id])}\n\n"
                 f"⚠️ Не забывайте чинить машины в тюнинге!",
            parse_mode='HTML'
        )
    else:
        await bot.answer_callback_query(callback_query.id, "❌ Слишком рано для сбора дохода!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "carsharing_command")
async def carsharing_from_income(callback_query: types.CallbackQuery):
    """Переход в каршеринг из команды доход"""
    await bot.answer_callback_query(callback_query.id)
    # Создаём псевдо-сообщение с правильным from_user
    message = callback_query.message
    message.from_user = callback_query.from_user
    await carsharing_command(message)

@dp.callback_query_handler(lambda c: c.data == "taxipark_command")
async def taxipark_from_income(callback_query: types.CallbackQuery):
    """Переход в таксопарк из команды доход"""
    await bot.answer_callback_query(callback_query.id)
    # Создаём псевдо-сообщение с правильным from_user
    message = callback_query.message
    message.from_user = callback_query.from_user
    await taxipark_command(message)

# ========== ИСПРАВЛЕННАЯ КОМАНДА МАШИНА ==========

@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['машина', 'авто', 'car', 'тачка'])
async def free_car_exact_command(message:types.Message): 
    uid=message.from_user.id 
    ensure_user_initialized(uid) 
    now=time.time() 
    
    decorations = get_event_decorations()
    
    if uid!=OWNER_ID and uid in last_use and now-last_use[uid]<COOLDOWN: 
        remaining = COOLDOWN - (now - last_use[uid]) 
        hours = int(remaining // 3600) 
        minutes = int((remaining % 3600) // 60) 
        seconds = int(remaining % 60) 
        
        progress_bar_length = 10 
        progress = (COOLDOWN - remaining) / COOLDOWN 
        filled = int(progress * progress_bar_length) 
        bar = "█" * filled + "▒" * (progress_bar_length - filled) 
        
        timer_text = ( 
            f"⏰ <b>ТАЙМЕР КУЛДАУНА</b>\n\n" 
            f"{bar} {progress*100:.0f}%\n\n" 
            f"🕐 До следующей машины:\n" 
            f"<b>{hours:02d}:{minutes:02d}:{seconds:02d}</b>\n\n" 
            f"<i>Осталось: {hours}ч {minutes}м {seconds}с</i>" 
        ) 
        
        await message.reply(timer_text, parse_mode='HTML') 
        return 
        
    car=await get_random_car_for_free(uid) 
    user_garage[uid].append(car) 
    user_balance[uid]+=500 
    last_use[uid]=now 
    
    update_quest_progress(uid, 'car_collected', 1)
    
    save_data() 
    
    wear_emoji = get_wear_emoji(car.get('wear', 100))
    
    caption = ( 
        f"🎁 <b>НОВАЯ МАШИНА!</b>\n" 
        f"<b>{car['name']}</b> — {car['rarity']}\n" 
        f"{decorations['money_emoji']} Оценка: <b>{format_money(car['value'])}</b>\n" 
        f"⚙️ HP: <b>{car['hp']}</b> | ACC: <b>{car['acc']}</b> | HND: <b>{car['handling']}</b>\n"
        f"{wear_emoji} Износ: <b>{car.get('wear', 100)}%</b>\n"
        f"🆔 ID: <code>{car['id']}</code>\n\n" 
        f"⏰ Следующая машина через 3 часа" 
    ) 
    
    try:
        if car.get('image_path') and os.path.exists(car.get('image_path')):
            with open(car['image_path'], 'rb') as photo:
                await message.reply_photo(photo, caption=caption, parse_mode='HTML')
        else:
            await message.reply(caption, parse_mode='HTML')
    except Exception as e:
        await message.reply(caption, parse_mode='HTML')

async def get_random_car_for_free(user_id:int): 
    # Обновляем каталог машин с учетом текущего события
    global cars
    cars = get_cars_with_events()
    
    # Проверяем событие и с шансом 2% выдаем ивентовую машину
    check_current_event()
    if current_event and random.random() < 0.02:
        event_cars = get_event_special_cars()
        car_name = random.choice(event_cars)
        event_name = EVENTS[current_event]["name"]
        return generate_car_data(car_name, event_name, user_id)
    
    # С шансом 1% выдаем скраповую машину
    if random.random() < 0.01:
        scrap_cars = cars.get('Скраповые', [])
        if scrap_cars:
            car_name = random.choice(scrap_cars)
            return generate_car_data(car_name, 'Скраповые', user_id)
    
    available_rarities = [k for k,v in cars.items() if v and k != 'Эксклюзивные' and not k.startswith('🎃') and not k.startswith('🎄') and not k.startswith('☀️')]
    if not available_rarities: 
        return generate_car_data('Default Model', 'Обычные', user_id) 

    # Применяем бонус события к весам
    event_bonus = get_event_bonus()
    weights = []
    for rarity in available_rarities:
        base_weight = CAR_WEIGHTS.get(rarity, 1)
        if rarity in ['Эпические', 'Легендарные']:
            # Увеличиваем шанс на редкие машины во время событий
            weights.append(base_weight * event_bonus)
        else:
            weights.append(base_weight)

    rarity = random.choices(available_rarities, weights=weights, k=1)[0] 
    models = cars.get(rarity, []) 
    if not models: 
        all_models = [name for lst in cars.values() for name in lst if lst != cars['Эксклюзивные'] and not lst.startswith('🎃') and not lst.startswith('🎄') and not lst.startswith('☀️')] 
        if not all_models: 
            return generate_car_data('Default Model', 'Обычные', user_id) 
        name = random.choice(all_models) 
        for r, lst in cars.items(): 
            if name in lst: 
                rarity = r 
                break 
    else: 
        name = random.choice(models) 

    return generate_car_data(name,rarity,user_id) 

# ========== ИСПРАВЛЕННАЯ КОМАНДА ЭКСКЛЮЗИВ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['эксклюзив', 'exclusive']) and m.from_user.id == OWNER_ID)
async def give_exclusive(message: types.Message):
    decorations = get_event_decorations()
    
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_username = message.reply_to_message.from_user.first_name
        
        available_exclusives = get_cars_with_events()['Эксклюзивные']
        if not available_exclusives:
            await message.reply("❌ Нет доступных эксклюзивных машин.")
            return
        
        car_name = random.choice(available_exclusives)
        exclusive_car = generate_car_data(car_name, 'Эксклюзивные', target_user_id)
        
        ensure_user_initialized(target_user_id)
        user_garage[target_user_id].append(exclusive_car)
        
        save_data()
        
        caption = (
            f"👑 <b>ЭКСКЛЮЗИВНАЯ МАШИНА ОТ АДМИНА!</b>\n"
            f"<b>{exclusive_car['name']}</b> — {exclusive_car['rarity']}\n"
            f"{decorations['money_emoji']} Оценка: <b>{format_money(exclusive_car['value'])}</b>\n"
            f"⚙️ HP: <b>{exclusive_car['hp']}</b> | ACC: <b>{exclusive_car['acc']}</b> | HND: <b>{exclusive_car['handling']}</b>\n"
            f"🆔 ID: <code>{exclusive_car['id']}</code>\n\n"
            f"💎 <i>Эта машина не продаётся и доступна только вам!</i>\n"
            f"🎁 Подарок от администратора"
        )
        
        try:
            if exclusive_car.get('image_path') and os.path.exists(exclusive_car.get('image_path')):
                with open(exclusive_car['image_path'], 'rb') as photo:
                    await bot.send_photo(target_user_id, photo, caption=caption, parse_mode='HTML')
                    await message.reply(f"✅ Эксклюзивная машина выдана пользователю {target_username}!")
            else:
                await bot.send_message(target_user_id, caption, parse_mode='HTML')
                await message.reply(f"✅ Эксклюзивная машина выдана пользователю {target_username}!")
        except Exception as e:
            await message.reply(f"❌ Не удалось отправить сообщение пользователю. Возможно, он не начинал диалог с ботом.")
    else:
        user_id = message.from_user.id
        
        available_exclusives = get_cars_with_events()['Эксклюзивные']
        if not available_exclusives:
            await message.reply("❌ Нет доступных эксклюзивных машин.")
            return
        
        car_name = random.choice(available_exclusives)
        exclusive_car = generate_car_data(car_name, 'Эксклюзивные', user_id)
        user_garage[user_id].append(exclusive_car)
        
        save_data()
        
        caption = (
            f"👑 <b>ЭКСКЛЮЗИВНАЯ МАШИНА!</b>\n"
            f"<b>{exclusive_car['name']}</b> — {exclusive_car['rarity']}\n"
            f"{decorations['money_emoji']} Оценка: <b>{format_money(exclusive_car['value'])}</b>\n"
            f"⚙️ HP: <b>{exclusive_car['hp']}</b> | ACC: <b>{exclusive_car['acc']}</b> | HND: <b>{exclusive_car['handling']}</b>\n"
            f"🆔 ID: <code>{exclusive_car['id']}</code>\n\n"
            f"💎 <i>Эта машина не продаётся и доступна только вам!</i>"
        )
        
        try:
            if exclusive_car.get('image_path') and os.path.exists(exclusive_car.get('image_path')):
                with open(exclusive_car['image_path'], 'rb') as photo:
                    await message.reply_photo(photo, caption=caption, parse_mode='HTML')
            else:
                await message.reply(caption, parse_mode='HTML')
        except Exception as e:
            await message.reply(caption, parse_mode='HTML')

# ========== ИСПРАВЛЕННЫЕ АДМИН КОМАНДЫ ==========

# ИСПРАВЛЕННАЯ КОМАНДА ДЛЯ ВЫДАЧИ ДЕНЕГ
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('деньги ') and m.from_user.id == OWNER_ID)
async def give_money(message: types.Message):
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            await message.reply("❌ Использование: деньги [сумма] [ID пользователя (опционально)]")
            return
        
        amount = int(parts[1])
        if amount <= 0:
            await message.reply("❌ Сумма должна быть положительной.")
            return
        
        if len(parts) >= 3:
            try:
                target_id = int(parts[2])
                ensure_user_initialized(target_id)
                user_balance[target_id] += amount
                
                try:
                    target_user = await bot.get_chat(target_id)
                    username = f"@{target_user.username}" if target_user.username else f"ID {target_id}"
                    await message.reply(f"✅ Выдано {format_money(amount)} пользователю {username}\n💰 Новый баланс: {format_money(user_balance[target_id])}")
                    
                    await bot.send_message(target_id, f"🎁 Администратор выдал вам {format_money(amount)}!\n💰 Ваш баланс: {format_money(user_balance[target_id])}")
                except:
                    await message.reply(f"✅ Выдано {format_money(amount)} пользователю ID {target_id}")
                
            except ValueError:
                await message.reply("❌ Неверный формат ID пользователя.")
                return
        else:
            user_balance[OWNER_ID] += amount
            await message.reply(f"✅ Вам выдано {format_money(amount)}\n💰 Новый баланс: {format_money(user_balance[OWNER_ID])}")
        
        save_data()
        
    except ValueError:
        await message.reply("❌ Неверный формат суммы.")

# ========== СИСТЕМА РАССЫЛКИ ==========

@dp.message_handler(commands=['рассылка'])
async def broadcast_command(message: types.Message):
    """Система рассылки сообщений всем пользователям"""
    if message.from_user.id != OWNER_ID:
        await message.reply("❌ Эта команда только для администратора!")
        return
    
    # Проверяем, есть ли текст после команды
    if not message.text or len(message.text.split()) < 2:
        await message.reply(
            "📢 <b>СИСТЕМА РАССЫЛКИ</b>\n\n"
            "Использование:\n"
            "<code>/рассылка ваш текст здесь</code>\n\n"
            "Или отправьте команду без текста, а затем бот запросит текст для рассылки.",
            parse_mode='HTML'
        )
        return
    
    # Если текст есть в команде
    broadcast_text = message.text.split(' ', 1)[1]
    await start_broadcast(message, broadcast_text)

async def start_broadcast(message: types.Message, text: str):
    """Запуск рассылки"""
    users = list(user_balance.keys())
    total_users = len(users)
    successful = 0
    failed = 0
    
    status_msg = await message.reply(f"📢 <b>Начинаю рассылку...</b>\n👥 Всего пользователей: {total_users}\n✅ Успешно: 0\n❌ Ошибок: 0", parse_mode='HTML')
    
    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                f"📢 <b>ОБЪЯВЛЕНИЕ ОТ АДМИНИСТРАЦИИ</b>\n\n{text}",
                parse_mode='HTML'
            )
            successful += 1
            
            # Обновляем статус каждые 10 отправок
            if (successful + failed) % 10 == 0:
                try:
                    await status_msg.edit_text(
                        f"📢 <b>Рассылка в процессе...</b>\n👥 Всего пользователей: {total_users}\n✅ Успешно: {successful}\n❌ Ошибок: {failed}",
                        parse_mode='HTML'
                    )
                except:
                    pass
            
            # Задержка чтобы не спамить
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed += 1
            print(f"Ошибка отправки пользователю {user_id}: {e}")
    
    # Финальный статус
    await status_msg.edit_text(
        f"🎉 <b>РАССЫЛКА ЗАВЕРШЕНА!</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Успешно: {successful}\n"
        f"❌ Ошибок: {failed}\n"
        f"📊 Охват: {(successful/total_users*100):.1f}%",
        parse_mode='HTML'
    )

# ========== МАГАЗИН С ИВЕНТОВЫМИ МАШИНАМИ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['магазин', 'shop', 'купить'])) 
async def shop(message:types.Message): 
    uid=message.from_user.id 
    ensure_user_initialized(uid) 
    
    decorations = get_event_decorations()
    
    text = f"{decorations['money_emoji']} <b>Ваш баланс:</b> {format_money(user_balance[uid])}\n\n"
    text += f"{decorations['shop_emoji']} <b>МАГАЗИН МАШИН</b>\n\n"
    
    current_cars = get_cars_with_events()
    
    for rarity in ["Обычные", "Редкие", "Эпические", "Легендарные"]:
        if rarity in current_cars and current_cars[rarity]:
            min_price, max_price = SHOP_PRICE_RANGES.get(rarity, (10000, 50000))
            text += f"<b>{rarity}:</b> ({min_price:,}$ - {max_price:,}$)\n"
            text += f"<i>Доступно {len(current_cars[rarity])} моделей</i>\n\n"
    
    # Показываем ивентовые машины только во время события
    check_current_event()
    if current_event:
        event_name = EVENTS[current_event]["name"]
        if event_name in current_cars and current_cars[event_name]:
            text += f"{decorations['main_emoji']} <b>{event_name}:</b> (500,000$ - 1,000,000$)\n"
            text += f"<i>Специальные машины на время события!</i>\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton(text=f'{decorations["shop_emoji"]} Купить машину', callback_data='shop_show_categories'))
    kb.add(types.InlineKeyboardButton(text='❌ Закрыть', callback_data='shop_close'))
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == 'shop_show_categories')
async def shop_show_categories(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    ensure_user_initialized(user_id)
    
    decorations = get_event_decorations()
    
    # Получаем актуальный каталог машин с учетом событий
    current_cars = get_cars_with_events()
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    ordered = ["Обычные","Редкие","Эпические","Легендарные"] 
    for key in ordered: 
        if key in current_cars and current_cars[key]:
            car_count = len(current_cars[key])
            min_p, max_p = SHOP_PRICE_RANGES.get(key, (10000, 50000))
            label = f"{key} ({car_count})"
            kb.insert(types.InlineKeyboardButton(text=label, callback_data=f'select_shop_rarity:{key}')) 
    
    # Добавляем ивентовые машины только во время события
    check_current_event()
    if current_event:
        event_name = EVENTS[current_event]["name"]
        if event_name in current_cars and current_cars[event_name]:
            event_car_count = len(current_cars[event_name])
            kb.insert(types.InlineKeyboardButton(
                text=f"{decorations['main_emoji']} {event_name} ({event_car_count})", 
                callback_data=f'select_shop_rarity:{event_name}'
            ))
    
    kb.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='shop_back_main'))
    
    text = f'{decorations["money_emoji"]} Баланс: {format_money(user_balance[user_id])}\n\n{decorations["shop_emoji"]} <b>Выберите категорию для покупки:</b>'
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML',
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('select_shop_rarity:')) 
async def process_select_shop_rarity(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    user_id = callback_query.from_user.id 
    rarity = callback_query.data.split(':',1)[1] 
    ensure_user_initialized(user_id) 

    decorations = get_event_decorations()
    
    # Получаем актуальный каталог машин
    current_cars = get_cars_with_events()

    available = current_cars.get(rarity, []) 
    if not available: 
        await bot.send_message(user_id, 'В этой категории пока нет доступных машин.') 
        return 

    # Premium category check
    if rarity in PREMIUM_RARITIES:
        try:
            if not await is_user_subscribed(user_id):
                await bot.send_message(user_id, '❌ Эта категория доступна только подписчикам.')
                return
        except Exception:
            await bot.send_message(user_id, '❌ Не удалось проверить подписку. Попробуйте позже.')
            return

    kb = types.InlineKeyboardMarkup(row_width=1) 
    
    # Определяем цену в зависимости от категории
    check_current_event()
    if current_event and rarity == EVENTS[current_event]["name"]:
        # Цена для ивентовых машин
        for car_name in available: 
            price = random.randint(500000, 1000000)  # Случайная цена от 500к до 1 ляма
            safe_car_name = car_name.replace(':', '|')
            kb.add(types.InlineKeyboardButton(
                text=f"{decorations['car_emoji']} {car_name} — {format_money(price)}", 
                callback_data=f'buy_car:{rarity}:{safe_car_name}:{price}'
            )) 
    else:
        # Цена для обычных категорий
        for car_name in available: 
            min_p, max_p = SHOP_PRICE_RANGES.get(rarity, (10000,50000)) 
            price = random.randint(min_p, max_p) 
            safe_car_name = car_name.replace(':', '|')
            kb.add(types.InlineKeyboardButton(
                text=f"{decorations['car_emoji']} {car_name} — {format_money(price)}", 
                callback_data=f'buy_car:{rarity}:{safe_car_name}:{price}'
            )) 

    kb.add(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='shop_back_to_categories')) 

    text = f"{decorations['money_emoji']} Баланс: {format_money(user_balance[user_id])}\n\n"
    text += f"{decorations['shop_emoji']} <b>Магазин — {rarity}</b>\nВыберите модель для покупки:"

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id, 
        message_id=callback_query.message.message_id, 
        text=text, 
        parse_mode='HTML', 
        reply_markup=kb
    ) 

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('buy_car:')) 
async def process_buy_car(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    user_id = callback_query.from_user.id 
    parts = callback_query.data.split(':') 
    
    if len(parts) != 4:
        await bot.send_message(user_id, 'Ошибка данных покупки.')
        return
        
    try: 
        rarity = parts[1]
        car_name = parts[2].replace('|', ':')
        price = int(parts[3]) 
    except Exception: 
        await bot.send_message(user_id, 'Ошибка данных покупки.') 
        return 

    ensure_user_initialized(user_id) 
    # Check premium category access
    if rarity in PREMIUM_RARITIES:
        try:
            if not await is_user_subscribed(user_id):
                await bot.send_message(user_id, '❌ Покупка этой машины доступна только подписчикам.')
                return
        except Exception:
            await bot.send_message(user_id, '❌ Не удалось проверить подписку. Попробуйте позже.')
            return
    if user_balance.get(user_id,0) < price: 
        await bot.send_message(user_id, f'❌ Недостаточно средств. Нужно {format_money(price)}') 
        return 

    decorations = get_event_decorations()

    # Получаем актуальный каталог машин
    current_cars = get_cars_with_events()
    
    # Проверяем доступность машины в текущем каталоге
    if car_name not in current_cars.get(rarity, []):
        await bot.send_message(user_id, '❌ Эта машина недоступна для покупки.') 
        return 

    new_car = generate_car_data(car_name, rarity, user_id) 
    new_car['value'] = price 
    user_garage[user_id].append(new_car) 
    user_balance[user_id] -= price 
    
    update_quest_progress(user_id, 'car_collected', 1)
    
    save_data() 

    success_text = (
        f"🎉 <b>МАШИНА КУПЛЕНА!</b> 🎉\n\n"
        f"{decorations['car_emoji']} <b>{new_car['name']}</b>\n"
        f"💎 Редкость: <b>{new_car['rarity']}</b>\n"
        f"{decorations['money_emoji']} Цена: <b>{format_money(price)}</b>\n"
        f"💰 Баланс: <b>{format_money(user_balance[user_id])}</b>\n"
        f"⚙️ Характеристики: HP {new_car['hp']} | ACC {new_car['acc']} | HND {new_car['handling']}\n\n"
        f"✅ Машина добавлена в ваш гараж!"
    )
    
    try: 
        if new_car.get('image_path') and os.path.exists(new_car.get('image_path')):
            with open(new_car['image_path'], 'rb') as photo:
                await bot.send_photo(user_id, photo, caption=success_text, parse_mode='HTML')
        else:
            await bot.send_message(user_id, success_text, parse_mode='HTML')
    except Exception as e:
        await bot.send_message(user_id, success_text, parse_mode='HTML')
    
    try: 
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id, 
            message_id=callback_query.message.message_id, 
            text=f"✅ Покупка завершена! {new_car['name']} добавлена в гараж.",
            reply_markup=None
        ) 
    except Exception: 
        pass 

@dp.callback_query_handler(lambda c: c.data == 'shop_back_to_categories') 
async def shop_back_to_categories(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    await shop_show_categories(callback_query)

@dp.callback_query_handler(lambda c: c.data == 'shop_back_main') 
async def shop_back_main(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id)
    message = callback_query.message
    message.from_user = callback_query.from_user
    await shop(message)

@dp.callback_query_handler(lambda c: c.data == 'shop_close') 
async def shop_close(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    try: 
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id) 
    except Exception: 
        pass 

# ========== ПРОДАЖА МАШИН ==========

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sell_id:')) 
async def callback_sell_by_id(callback_query: types.CallbackQuery): 
    user_id = callback_query.from_user.id 
    car_id = callback_query.data.split(':',1)[1] 
    await bot.answer_callback_query(callback_query.id) 
    cars_list = user_garage.get(user_id, []) 
    
    for i, car in enumerate(cars_list): 
        if car.get('id') == car_id: 
            if car.get('sellable') is False: 
                await bot.answer_callback_query(callback_query.id, "❌ Эта машина эксклюзивная и не продаётся!", show_alert=True) 
                return 
            
            sold_value = car['value']
            sold = cars_list.pop(i) 
            user_balance[user_id] += sold_value 
            if car_id in car_owner_map: 
                del car_owner_map[car_id] 
                
            update_quest_progress(user_id, 'car_sold', 1)
            update_quest_progress(user_id, 'money_earned', sold_value)
            
            save_data() 
            
            total = len(cars_list) 
            if total == 0: 
                try: 
                    decorations = get_event_decorations()
                    await bot.edit_message_text( 
                        chat_id=callback_query.message.chat.id, 
                        message_id=callback_query.message.message_id, 
                        text=f"{decorations['garage_emoji']} <b>Твой гараж пуст!</b>\n{decorations['money_emoji']} Продано: {format_money(sold_value)}\n💳 Баланс: {format_money(user_balance[user_id])}", 
                        parse_mode='HTML', 
                        reply_markup=None 
                    ) 
                except Exception: 
                    pass 
            else: 
                new_index = min(i, total-1) 
                new_car = cars_list[new_index] 
                
                await send_car_card(
                    callback_query.message.chat.id,
                    new_car,
                    new_index,
                    total,
                    edit_message={
                        'chat_id': callback_query.message.chat.id,
                        'message_id': callback_query.message.message_id
                    }
                )
            return 
    
    await bot.answer_callback_query(callback_query.id, "❌ Машина не найдена в гараже.", show_alert=True)

# ========== ТЮНИНГ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['тюнинг', 'улучшить', 'tune'])) 
async def tune_cmd(message: types.Message): 
    uid = message.from_user.id 
    ensure_user_initialized(uid) 
    cars_list = user_garage.get(uid, []) 
    if not cars_list: 
        await message.reply('У тебя нет машин для тюнинга.') 
        return 
    kb = types.InlineKeyboardMarkup(row_width=1) 
    for c in cars_list: 
        kb.add(types.InlineKeyboardButton(text=f"{c['name']} (ID {c['id']})", callback_data=f'tune_select:{c["id"]}')) 
    await message.reply('Выбери машину для тюнинга:', reply_markup=kb) 

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tune_select:')) 
async def tune_select(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    car_id = callback_query.data.split(':',1)[1] 
    uid = callback_query.from_user.id 
    car = next((c for c in user_garage.get(uid, []) if c.get('id')==car_id), None) 
    if not car: 
        await bot.answer_callback_query(callback_query.id, 'Машина не найдена.', show_alert=True) 
        return 
    price_hp = max(1000, int(car.get('value',10000) * 0.05)) 
    price_acc = max(1000, int(car.get('value',10000) * 0.04)) 
    price_hand = max(1000, int(car.get('value',10000) * 0.04)) 
    kb = types.InlineKeyboardMarkup(row_width=1) 
    kb.add(types.InlineKeyboardButton(text=f"+10% HP — {price_hp:,}$", callback_data=f'tune_buy:{car_id}:hp:{price_hp}')) 
    kb.add(types.InlineKeyboardButton(text=f"+10% ACC — {price_acc:,}$", callback_data=f'tune_buy:{car_id}:acc:{price_acc}')) 
    kb.add(types.InlineKeyboardButton(text=f"+10% HND — {price_hand:,}$", callback_data=f'tune_buy:{car_id}:handling:{price_hand}')) 
    await bot.send_message(uid, f"Тюнинг — {car['name']}\nHP: {car['hp']} | ACC: {car['acc']} | HND: {car['handling']}", reply_markup=kb) 

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tune_buy:')) 
async def tune_buy(callback_query: types.CallbackQuery): 
    await bot.answer_callback_query(callback_query.id) 
    parts = callback_query.data.split(':') 
    if len(parts) != 4: 
        return 
    car_id = parts[1] 
    stat = parts[2] 
    try: 
        price = int(parts[3]) 
    except Exception: 
        await bot.answer_callback_query(callback_query.id, 'Ошибка данных.', show_alert=True) 
        return 
    uid = callback_query.from_user.id 
    ensure_user_initialized(uid) 
    if user_balance.get(uid,0) < price: 
        await bot.answer_callback_query(callback_query.id, 'Недостаточно средств.', show_alert=True) 
        return 
    car = next((c for c in user_garage.get(uid, []) if c.get('id')==car_id), None) 
    if not car: 
        await bot.answer_callback_query(callback_query.id, 'Машина не найдена.', show_alert=True) 
        return 
    increment = max(1, int(car.get(stat,0) * 0.1)) 
    car[stat] = car.get(stat,0) + increment 
    user_balance[uid] -= price 
    
    update_quest_progress(uid, 'car_tuned', 1)
    
    save_data() 
    await bot.send_message(uid, f"✅ Тюнинг применён: {car['name']} — +{increment} {stat.upper()}\nНовый статус: HP {car['hp']} | ACC {car['acc']} | HND {car['handling']}\nБаланс: {user_balance[uid]:,}$")

# ========== БАЛАНС И ПРОФИЛЬ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['баланс', 'деньги', 'balance', 'money'])) 
async def show_balance(message:types.Message): 
    uid=message.from_user.id 
    ensure_user_initialized(uid) 
    decorations = get_event_decorations()
    await message.reply(f"{decorations['money_emoji']} Баланс: {format_money(user_balance[uid])}") 

@dp.message_handler(lambda m: m.text and is_command_message(m, ['профиль', 'profile', 'стата'])) 
async def profile(message:types.Message): 
    uid=message.from_user.id 
    ensure_user_initialized(uid) 
    init_user_quests(uid)
    
    decorations = get_event_decorations()
    
    progress = user_quests[uid]['progress']
    total_cars = len(user_garage[uid])
    legendary_count = sum(1 for car in user_garage[uid] if car.get('rarity') == 'Легендарные')
    exclusive_count = sum(1 for car in user_garage[uid] if car.get('rarity') == 'Эксклюзивные')
    
    # Считаем ивентовые машины
    event_car_count = 0
    check_current_event()
    if current_event:
        event_name = EVENTS[current_event]["name"]
        event_car_count = sum(1 for car in user_garage[uid] if car.get('rarity') == event_name)
    
    event_message = get_event_message()
    
    text = (
        f"👤 <b>ПРОФИЛЬ ИГРОКА</b>\n\n"
    )
    
    if event_message:
        text += f"{event_message}\n\n"
    
    text += (
        f"{decorations['money_emoji']} Баланс: {format_money(user_balance[uid])}\n"
        f"{decorations['garage_emoji']} Машин в гараже: {total_cars}\n"
        f"🌟 Легендарных: {legendary_count}\n"
    )
    
    if current_event:
        text += f"{decorations['main_emoji']} {EVENTS[current_event]['name']}: {event_car_count}\n"
    
    text += (
        f"💎 Эксклюзивных: {exclusive_count}\n\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"• Всего машин получено: {progress['total_cars_collected']}\n"
        f"• Побед в гонках: {progress['total_races_won']}\n"
        f"• Всего заработано: {format_money(progress['total_money_earned'])}\n"
        f"• Создано крафтом: {progress['total_cars_crafted']}\n"
        f"• Выиграно аукционов: {progress['total_auctions_won']}"
    )
    await message.reply(text, parse_mode='HTML')

# ========== ЕЖЕДНЕВНЫЙ БОНУС ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['бонус', 'ежедневный', 'подарок']))
async def daily_bonus(message: types.Message):
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    
    now = time.time()
    last_bonus = daily_gift.get(user_id, 0)
    
    if now - last_bonus < 24 * 60 * 60:
        remaining = 24 * 60 * 60 - (now - last_bonus)
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await message.reply(f"⏰ Следующий бонус через {hours}ч {minutes}м")
        return
    
    bonus_type = random.choice(['money', 'car', 'big_money'])
    
    if bonus_type == 'money':
        amount = random.randint(5000, 20000)
        user_balance[user_id] += amount
        text = f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС!</b>\n\n💰 Вы получили {format_money(amount)}"
    
    elif bonus_type == 'big_money':
        amount = random.randint(25000, 50000)
        user_balance[user_id] += amount
        text = f"🎁 <b>СУПЕР БОНУС!</b>\n\n💰 Вы получили {format_money(amount)}"
    
    else:
        car = await get_random_car_for_free(user_id)
        user_garage[user_id].append(car)
        decorations = get_event_decorations()
        text = f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС!</b>\n\n{decorations['car_emoji']} Вы получили {car['name']} ({car['rarity']})"
    
    daily_gift[user_id] = now
    if bonus_type != 'car':
        update_quest_progress(user_id, 'money_earned', amount)
    else:
        update_quest_progress(user_id, 'car_collected', 1)
    
    save_data()
    await message.reply(text, parse_mode='HTML')

# ========== ТОП И СТАТИСТИКА ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['топ', 'рейтинг', 'лидеры']))
async def top_players(message: types.Message):
    sorted_players = sorted(user_balance.items(), key=lambda x: x[1], reverse=True)[:10]
    
    text = "🏆 <b>ТОП-10 ИГРОКОВ ПО БАЛАНСУ</b>\n\n"
    
    for i, (player_id, balance) in enumerate(sorted_players, 1):
        try:
            user = await bot.get_chat(player_id)
            username = f"@{user.username}" if user.username else f"Игрок {player_id}"
        except:
            username = f"Игрок {player_id}"
        
        car_count = len(user_garage.get(player_id, []))
        text += f"{i}. {username}\n   💰 {format_money(balance)} | 🚗 {car_count} машин\n"
    
    await message.reply(text, parse_mode='HTML')

@dp.message_handler(lambda m: m.text and is_command_message(m, ['статистика', 'стата', 'stats']))
async def server_stats(message: types.Message):
    total_players = len(user_balance)
    total_cars = sum(len(garage) for garage in user_garage.values())
    total_money = sum(user_balance.values())
    
    richest_player = max(user_balance.items(), key=lambda x: x[1]) if user_balance else (0, 0)
    biggest_garage = max(user_garage.items(), key=lambda x: len(x[1])) if user_garage else (0, [])
    
    event_message = get_event_message()
    
    text = (
        f"📊 <b>СТАТИСТИКА СЕРВЕРА</b>\n\n"
    )
    
    if event_message:
        text += f"{event_message}\n\n"
    
    text += (
        f"👥 Всего игроков: {total_players}\n"
        f"🚗 Всего машин: {total_cars}\n"
        f"💰 Общий баланс: {format_money(total_money)}\n\n"
        f"🏆 <b>Рекорды:</b>\n"
        f"• Самый богатый: {format_money(richest_player[1])}\n"
        f"• Самый большой гараж: {len(biggest_garage[1])} машин"
    )
    
    await message.reply(text, parse_mode='HTML')

# ========== СИСТЕМА ГОНОК С ДВУМЯ УЧАСТНИКАМИ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['гонка', 'race', 'вызвать']))
async def race_command(message: types.Message):
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    
    cars_list = user_garage.get(user_id, [])
    if not cars_list:
        await message.reply("❌ У вас нет машин для участия в гонках!")
        return
    
    # Если это ответ на сообщение - вызываем пользователя
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_username = message.reply_to_message.from_user.first_name
        
        if target_user_id == user_id:
            await message.reply("❌ Нельзя вызвать самого себя!")
            return
            
        ensure_user_initialized(target_user_id)
        target_cars = user_garage.get(target_user_id, [])
        if not target_cars:
            await message.reply("❌ У этого пользователя нет машин для гонок!")
            return
        
        # Показываем выбор машины для вызывающего
        text = f"🏁 <b>ВЫЗОВ НА ГОНКУ</b>\n\nВы вызываете {target_username} на гонку!\nВыберите свою машину:"
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        for car in cars_list:
            kb.add(types.InlineKeyboardButton(
                text=f"{car['name']} (HP: {car['hp']} | ACC: {car['acc']} | HND: {car['handling']})",
                callback_data=f'race_challenge:{target_user_id}:{car["id"]}'
            ))
        
        kb.add(types.InlineKeyboardButton(text='❌ Отмена', callback_data='race_cancel'))
        
        await message.reply(text, parse_mode='HTML', reply_markup=kb)
    else:
        # Обычный выбор машины для гонки
        text = "🏁 <b>СИСТЕМА ГОНОК</b>\n\nВыберите действие:"
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton(text='🚀 Быстрая гонка', callback_data='race_quick'))
        kb.add(types.InlineKeyboardButton(text='👥 Вызвать друга', callback_data='race_invite_info'))
        
        await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == 'race_invite_info')
async def race_invite_info(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    text = (
        "👥 <b>ВЫЗОВ НА ГОНКУ</b>\n\n"
        "Чтобы вызвать друга на гонку:\n"
        "1. Ответьте на сообщение друга командой <b>гонка</b>\n"
        "2. Или отправьте команду <b>гонка @username</b>\n\n"
        "Оба участника должны иметь хотя бы одну машину в гараже!"
    )
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('race_challenge:'))
async def race_challenge_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    parts = callback_query.data.split(':')
    target_user_id = int(parts[1])
    car_id = parts[2]
    
    # Находим машину вызывающего
    cars_list = user_garage.get(user_id, [])
    challenger_car = None
    for car in cars_list:
        if car.get('id') == car_id:
            challenger_car = car
            break
    
    if not challenger_car:
        await bot.send_message(user_id, "❌ Машина не найдена!")
        return
    
    # Создаем приглашение на гонку
    race_id = generate_unique_id()
    race_invitations[race_id] = {
        'challenger_id': user_id,
        'challenger_car': challenger_car,
        'target_id': target_user_id,
        'created_at': time.time()
    }
    
    # Отправляем приглашение целевому пользователю
    try:
        target_user = await bot.get_chat(target_user_id)
        username = target_user.first_name
        
        text = (
            f"🏁 <b>ВЫЗОВ НА ГОНКУ!</b>\n\n"
            f"Пользователь {callback_query.from_user.first_name} вызывает вас на гонку!\n"
            f"🚗 Его машина: {challenger_car['name']}\n"
            f"💪 Характеристики: HP {challenger_car['hp']} | ACC {challenger_car['acc']} | HND {challenger_car['handling']}\n\n"
            f"Выберите свою машину для гонки:"
        )
        
        target_cars = user_garage.get(target_user_id, [])
        kb = types.InlineKeyboardMarkup(row_width=1)
        for car in target_cars:
            kb.add(types.InlineKeyboardButton(
                text=f"{car['name']} (HP: {car['hp']} | ACC: {car['acc']} | HND: {car['handling']})",
                callback_data=f'race_accept:{race_id}:{car["id"]}'
            ))
        
        kb.add(types.InlineKeyboardButton(text='❌ Отклонить', callback_data=f'race_decline:{race_id}'))
        
        await bot.send_message(target_user_id, text, parse_mode='HTML', reply_markup=kb)
        await bot.send_message(user_id, f"✅ Вызов отправлен {username}! Ожидайте ответа...")
        
    except Exception as e:
        await bot.send_message(user_id, f"❌ Не удалось отправить вызов пользователю. Возможно, он не начинал диалог с ботом.")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('race_accept:'))
async def race_accept_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    parts = callback_query.data.split(':')
    race_id = parts[1]
    car_id = parts[2]
    
    if race_id not in race_invitations:
        await bot.send_message(user_id, "❌ Приглашение на гонку устарело или было отменено!")
        return
    
    invitation = race_invitations[race_id]
    if user_id != invitation['target_id']:
        await bot.send_message(user_id, "❌ Это приглашение не для вас!")
        return
    
    # Находим машину принимающего
    cars_list = user_garage.get(user_id, [])
    target_car = None
    for car in cars_list:
        if car.get('id') == car_id:
            target_car = car
            break
    
    if not target_car:
        await bot.send_message(user_id, "❌ Машина не найдена!")
        return
    
    challenger_id = invitation['challenger_id']
    challenger_car = invitation['challenger_car']
    
    # Удаляем приглашение
    del race_invitations[race_id]
    
    # Создаем активную гонку
    active_races[race_id] = {
        'player1_id': challenger_id,
        'player1_car': challenger_car,
        'player2_id': user_id,
        'player2_car': target_car,
        'started_at': time.time()
    }
    
    # Уведомляем обоих участников
    await bot.send_message(
        challenger_id,
        f"✅ {callback_query.from_user.first_name} принял ваш вызов на гонку!\n"
        f"🚗 Его машина: {target_car['name']}\n"
        f"💪 Характеристики: HP {target_car['hp']} | ACC {target_car['acc']} | HND {target_car['handling']}\n\n"
        f"🏁 Гонка начинается..."
    )
    
    # Запускаем гонку
    await start_race(race_id)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('race_decline:'))
async def race_decline_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    race_id = callback_query.data.split(':')[1]
    
    if race_id not in race_invitations:
        await bot.send_message(user_id, "❌ Приглашение на гонку устарело или было отменено!")
        return
    
    invitation = race_invitations[race_id]
    challenger_id = invitation['challenger_id']
    
    # Удаляем приглашение
    del race_invitations[race_id]
    
    # Уведомляем вызывающего
    await bot.send_message(challenger_id, f"❌ {callback_query.from_user.first_name} отклонил ваш вызов на гонку.")
    await bot.send_message(user_id, "✅ Вы отклонили вызов на гонку.")

@dp.callback_query_handler(lambda c: c.data == 'race_quick')
async def race_quick_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    ensure_user_initialized(user_id)
    
    cars_list = user_garage.get(user_id, [])
    if not cars_list:
        await bot.send_message(user_id, "❌ У вас нет машин для участия в гонках!")
        return
    
    # Показываем список машин для выбора
    text = "🏁 <b>ВЫБОР МАШИНЫ ДЛЯ БЫСТРОЙ ГОНКИ</b>\n\nВыберите машину для участия в гонке:"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for car in cars_list:
        kb.add(types.InlineKeyboardButton(
            text=f"{car['name']} (HP: {car['hp']} | ACC: {car['acc']} | HND: {car['handling']})",
            callback_data=f'race_select:{car["id"]}'
        ))
    
    kb.add(types.InlineKeyboardButton(text='❌ Отмена', callback_data='race_cancel'))
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML',
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('race_select:'))
async def race_selected(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    car_id = callback_query.data.split(':', 1)[1]
    
    cars_list = user_garage.get(user_id, [])
    selected_car = None
    for car in cars_list:
        if car.get('id') == car_id:
            selected_car = car
            break
    
    if not selected_car:
        await bot.send_message(user_id, "❌ Машина не найдена!")
        return
    
    # Анимация гонки
    race_messages = [
        "🏁 <b>ГОНКА НАЧИНАЕТСЯ!</b>\nМашины выстраиваются на стартовой линии...",
        "🚦 <b>СИГНАЛ СТАРТА!</b>\nВсе машины рвутся вперед!",
        "🔄 <b>ПЕРВЫЙ ПОВОРОТ</b>\nМашины входят в сложный поворот...",
        "💨 <b>ПРЯМАЯ ДОРОГА</b>\nМаксимальная скорость на прямой!",
        "🏎️ <b>ФИНИШНАЯ ЧЕРТА</b>\nМашины приближаются к финишу...",
        "🎯 <b>ФИНИШ!</b>\nПодводим итоги гонки..."
    ]
    
    # Отправляем начальное сообщение
    message = await bot.send_message(
        callback_query.message.chat.id,
        f"🏁 <b>ПОДГОТОВКА К ГОНКЕ</b>\n\n"
        f"🚗 Ваша машина: <b>{selected_car['name']}</b>\n"
        f"💪 Характеристики: HP {selected_car['hp']} | ACC {selected_car['acc']} | HND {selected_car['handling']}",
        parse_mode='HTML'
    )
    
    # Анимация гонки с задержками
    for i, race_msg in enumerate(race_messages):
        await asyncio.sleep(2)  # Задержка 2 секунды между этапами
        
        try:
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=message.message_id,
                text=race_msg,
                parse_mode='HTML'
            )
        except:
            pass
    
    # Расчет результата гонки
    await asyncio.sleep(1)  # Дополнительная задержка перед результатом
    
    # Шанс победы на основе характеристик машины
    win_chance = min(90, (selected_car['hp'] * 0.1 + selected_car['acc'] * 0.15 + selected_car['handling'] * 0.15))
    is_win = random.random() * 100 < win_chance
    
    if is_win:
        reward = random.randint(5000, 15000)
        user_balance[user_id] += reward
        update_quest_progress(user_id, 'race_won', 1)
        update_quest_progress(user_id, 'money_earned', reward)
        
        result_text = (
            f"🎉 <b>ПОБЕДА В ГОНКЕ!</b>\n\n"
            f"🚗 Ваша машина: <b>{selected_car['name']}</b>\n"
            f"💪 Характеристики: HP {selected_car['hp']} | ACC {selected_car['acc']} | HND {selected_car['handling']}\n"
            f"💰 Выигрыш: {format_money(reward)}\n"
            f"🎯 Шанс победы: {win_chance:.1f}%\n\n"
            f"🎉 Поздравляем с победой!"
        )
    else:
        result_text = (
            f"🏁 <b>ПОРАЖЕНИЕ В ГОНКЕ</b>\n\n"
            f"🚗 Ваша машина: <b>{selected_car['name']}</b>\n"
            f"💪 Характеристики: HP {selected_car['hp']} | ACC {selected_car['acc']} | HND {selected_car['handling']}\n"
            f"🎯 Шанс победы: {win_chance:.1f}%\n\n"
            f"😔 В следующий раз повезёт!"
        )
    
    save_data()
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=message.message_id,
            text=result_text,
            parse_mode='HTML'
        )
    except:
        await bot.send_message(
            callback_query.message.chat.id,
            result_text,
            parse_mode='HTML'
        )

async def start_race(race_id):
    """Запускает гонку между двумя игроками"""
    if race_id not in active_races:
        return
    
    race = active_races[race_id]
    player1_id = race['player1_id']
    player2_id = race['player2_id']
    player1_car = race['player1_car']
    player2_car = race['player2_car']
    
    # Уведомляем обоих участников о начале гонки
    race_messages = [
        "🏁 <b>ГОНКА НАЧИНАЕТСЯ!</b>\nМашины выстраиваются на стартовой линии...",
        "🚦 <b>СИГНАЛ СТАРТА!</b>\nВсе машины рвутся вперед!",
        "🔄 <b>ПЕРВЫЙ ПОВОРОТ</b>\nМашины входят в сложный поворот...",
        "💨 <b>ПРЯМАЯ ДОРОГА</b>\nМаксимальная скорость на прямой!",
        "🏎️ <b>ФИНИШНАЯ ЧЕРТА</b>\nМашины приближаются к финишу...",
        "🎯 <b>ФИНИШ!</b>\nПодводим итоги гонки..."
    ]
    
    # Отправляем начальные сообщения
    msg1 = await bot.send_message(player1_id, "🏁 <b>ПОДГОТОВКА К ГОНКЕ</b>\n\nГонка начинается...")
    msg2 = await bot.send_message(player2_id, "🏁 <b>ПОДГОТОВКА К ГОНКЕ</b>\n\nГонка начинается...")
    
    # Анимация гонки с задержками
    for i, race_msg in enumerate(race_messages):
        await asyncio.sleep(2)
        
        try:
            await bot.edit_message_text(
                chat_id=player1_id,
                message_id=msg1.message_id,
                text=race_msg,
                parse_mode='HTML'
            )
            await bot.edit_message_text(
                chat_id=player2_id,
                message_id=msg2.message_id,
                text=race_msg,
                parse_mode='HTML'
            )
        except:
            pass
    
    # Расчет результата гонки
    await asyncio.sleep(1)
    
    # Расчет шансов победы на основе характеристик
    player1_power = player1_car['hp'] * 0.4 + player1_car['acc'] * 0.3 + player1_car['handling'] * 0.3
    player2_power = player2_car['hp'] * 0.4 + player2_car['acc'] * 0.3 + player2_car['handling'] * 0.3
    
    total_power = player1_power + player2_power
    player1_chance = (player1_power / total_power) * 100
    player2_chance = (player2_power / total_power) * 100
    
    # Определяем победителя
    winner_id = player1_id if random.random() * 100 < player1_chance else player2_id
    loser_id = player2_id if winner_id == player1_id else player1_id
    
    winner_car = player1_car if winner_id == player1_id else player2_car
    loser_car = player2_car if winner_id == player1_id else player1_car
    
    # Награда за победу
    reward = random.randint(10000, 25000)
    user_balance[winner_id] += reward
    
    # Обновляем квесты
    update_quest_progress(winner_id, 'race_won', 1)
    update_quest_progress(winner_id, 'money_earned', reward)
    
    # Результаты гонки
    winner_text = (
        f"🎉 <b>ПОБЕДА В ГОНКЕ!</b>\n\n"
        f"🚗 Ваша машина: <b>{winner_car['name']}</b>\n"
        f"🚗 Машина соперника: <b>{loser_car['name']}</b>\n"
        f"💰 Выигрыш: {format_money(reward)}\n"
        f"🎯 Ваш шанс победы: {player1_chance if winner_id == player1_id else player2_chance:.1f}%\n\n"
        f"🏆 Поздравляем с победой!"
    )
    
    loser_text = (
        f"🏁 <b>ПОРАЖЕНИЕ В ГОНКЕ</b>\n\n"
        f"🚗 Ваша машина: <b>{loser_car['name']}</b>\n"
        f"🚗 Машина победителя: <b>{winner_car['name']}</b>\n"
        f"🎯 Ваш шанс победы: {player2_chance if winner_id == player1_id else player1_chance:.1f}%\n\n"
        f"😔 В следующий раз повезёт!"
    )
    
    # Отправляем результаты
    await bot.send_message(winner_id, winner_text, parse_mode='HTML')
    await bot.send_message(loser_id, loser_text, parse_mode='HTML')
    
    # Удаляем активную гонку
    del active_races[race_id]
    save_data()

@dp.callback_query_handler(lambda c: c.data == 'race_cancel')
async def race_cancel(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="❌ Участие в гонке отменено.",
        parse_mode='HTML'
    )

# ========== ОБМЕН ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['обмен', 'trade', 'обменяться']))
async def trade_command(message: types.Message):
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    
    cars_list = user_garage.get(user_id, [])
    if len(cars_list) < 2:
        await message.reply("❌ Для обмена нужно как минимум 2 машины в гараже!")
        return
    
    text = (
        "🔄 <b>СИСТЕМА ОБМЕНА МАШИН</b>\n\n"
        "Вы можете обменять одну из своих машин на случайную машину другого игрока.\n"
        "При обмене вы получаете машину случайной редкости!\n\n"
        "💡 <i>Выберите машину для обмена:</i>"
    )
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for car in cars_list:
        if car.get('sellable', True):
            kb.add(types.InlineKeyboardButton(
                text=f"{car['name']} ({car['rarity']}) - ID: {car['id']}",
                callback_data=f'trade_car:{car["id"]}'
            ))
    
    kb.add(types.InlineKeyboardButton(text='❌ Отмена', callback_data='trade_cancel'))
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('trade_car:'))
async def process_trade(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    car_id = callback_query.data.split(':', 1)[1]
    
    cars_list = user_garage.get(user_id, [])
    trade_car = None
    for i, car in enumerate(cars_list):
        if car.get('id') == car_id:
            trade_car = cars_list.pop(i)
            break
    
    if not trade_car:
        await bot.answer_callback_query(callback_query.id, "❌ Машина не найдена!", show_alert=True)
        return
    
    new_car = await get_random_car_for_free(user_id)
    user_garage[user_id].append(new_car)
    
    if trade_car['id'] in car_owner_map:
        del car_owner_map[trade_car['id']]
    
    save_data()
    
    text = (
        f"🔄 <b>ОБМЕН ЗАВЕРШЁН!</b>\n\n"
        f"📤 Вы отдали: <b>{trade_car['name']}</b> ({trade_car['rarity']})\n"
        f"📥 Получили: <b>{new_car['name']}</b> ({new_car['rarity']})\n\n"
        f"💪 Новые характеристики:\n"
        f"HP: {new_car['hp']} | ACC: {new_car['acc']} | HND: {new_car['handling']}\n\n"
        f"🎉 Удачного обмена!"
    )
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data == 'trade_cancel')
async def cancel_trade(callback_query: types.CallbackQuery):
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="❌ Обмен отменён.",
        parse_mode='HTML'
    )

# ========== СИСТЕМА АУКЦИОНОВ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['аукцион', 'аукцион создать', 'аукц', 'аукц создать']))
async def auction_command(message: types.Message):
    user_id = message.from_user.id
    
    if 'создать' in message.text.lower() and user_id == OWNER_ID:
        await create_auction_command(message)
        return
    
    await show_auctions(message)

async def show_auctions(message: types.Message):
    """Показать список активных аукционов"""
    if not auctions:
        await message.reply(
            "🏪 <b>АУКЦИОННЫЙ ДОМ</b>\n\n"
            "❌ В данный момент нет активных аукционов.\n\n"
            "💡 Администратор может создать аукцион командой: <code>аукцион создать</code>"
        )
        return
    
    text = "🏪 <b>АКТИВНЫЕ АУКЦИОНЫ</b>\n\n"
    
    for auction_id, auction in auctions.items():
        time_left = auction['end_time'] - time.time()
        if time_left <= 0:
            continue
            
        hours = int(time_left // 3600)
        minutes = int((time_left % 3600) // 60)
        
        text += f"🎯 <b>Аукцион #{auction_id}</b>\n"
        text += f"🚗 Машина: {auction['car']['name']} ({auction['car']['rarity']})\n"
        text += f"💰 Текущая ставка: {format_money(auction['current_bid'])}\n"
        text += f"⏰ Осталось: {hours:02d}:{minutes:02d}\n"
        text += f"🆔 ID: <code>{auction_id}</code>\n\n"
    
    text += "💡 Для участия используйте: <code>ставка [ID] [сумма]</code>"
    
    await message.reply(text, parse_mode='HTML')

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('аукцион создать') and m.from_user.id == OWNER_ID)
async def create_auction_command(message: types.Message):
    """Создание нового аукциона (только для админа)"""
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    
    cars_list = user_garage.get(user_id, [])
    if not cars_list:
        await message.reply("❌ У вас нет машин для выставления на аукцион!")
        return
    
    text = "🏪 <b>СОЗДАНИЕ АУКЦИОНА</b>\n\nВыберите машину для выставления на аукцион:"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for car in cars_list:
        if car.get('sellable', True):
            kb.add(types.InlineKeyboardButton(
                text=f"{car['name']} ({car['rarity']}) - {format_money(car['value'])}",
                callback_data=f'auction_create:{car["id"]}'
            ))
    
    kb.add(types.InlineKeyboardButton(text='❌ Отмена', callback_data='auction_cancel'))
    
    await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('auction_create:'))
async def auction_create_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    car_id = callback_query.data.split(':', 1)[1]
    
    cars_list = user_garage.get(user_id, [])
    auction_car = None
    for i, car in enumerate(cars_list):
        if car.get('id') == car_id:
            auction_car = cars_list.pop(i)
            break
    
    if not auction_car:
        await bot.send_message(user_id, "❌ Машина не найдена!")
        return
    
    # Создаем аукцион
    auction_id = generate_unique_id()
    start_price = max(auction_car['value'] // 2, 10000)
    
    auctions[auction_id] = {
        'car': auction_car,
        'seller_id': user_id,
        'current_bid': start_price,
        'highest_bidder': None,
        'start_time': time.time(),
        'end_time': time.time() + 24 * 60 * 60,  # 24 часа
        'min_bid_increment': max(start_price // 10, 1000)
    }
    
    user_bids[auction_id] = {}
    
    # Удаляем машину из гаража продавца
    if auction_car['id'] in car_owner_map:
        del car_owner_map[auction_car['id']]
    
    save_data()
    
    await bot.send_message(
        user_id,
        f"✅ <b>АУКЦИОН СОЗДАН!</b>\n\n"
        f"🚗 Машина: {auction_car['name']}\n"
        f"💎 Редкость: {auction_car['rarity']}\n"
        f"💰 Начальная цена: {format_money(start_price)}\n"
        f"🆔 ID аукциона: <code>{auction_id}</code>\n\n"
        f"⏰ Аукцион закончится через 24 часа",
        parse_mode='HTML'
    )
    
    # Уведомляем всех пользователей о новом аукционе
    for uid in user_balance.keys():
        if uid != user_id:
            try:
                await bot.send_message(
                    uid,
                    f"🎉 <b>НОВЫЙ АУКЦИОН!</b>\n\n"
                    f"🚗 {auction_car['name']} ({auction_car['rarity']})\n"
                    f"💰 Начальная цена: {format_money(start_price)}\n"
                    f"🆔 ID: <code>{auction_id}</code>\n\n"
                    f"💡 Используйте: <code>ставка {auction_id} [сумма]</code>",
                    parse_mode='HTML'
                )
            except:
                pass

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('ставка '))
async def place_bid_command(message: types.Message):
    """Размещение ставки на аукционе"""
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 3:
            await message.reply("❌ Использование: ставка [ID_аукциона] [сумма]")
            return
        
        auction_id = parts[1]
        bid_amount = int(parts[2])
        
        if auction_id not in auctions:
            await message.reply("❌ Аукцион не найден!")
            return
        
        auction = auctions[auction_id]
        
        # Проверяем, не закончился ли аукцион
        if time.time() > auction['end_time']:
            await message.reply("❌ Аукцион уже завершен!")
            return
        
        # Проверяем, достаточно ли денег
        if user_balance[user_id] < bid_amount:
            await message.reply(f"❌ Недостаточно средств! Ваш баланс: {format_money(user_balance[user_id])}")
            return
        
        # Проверяем, что ставка выше текущей
        min_bid = auction['current_bid'] + auction['min_bid_increment']
        if bid_amount < min_bid:
            await message.reply(f"❌ Минимальная ставка: {format_money(min_bid)}")
            return
        
        # Возвращаем деньги предыдущему участнику
        if auction['highest_bidder'] and auction['highest_bidder'] in user_balance:
            user_balance[auction['highest_bidder']] += auction['current_bid']
        
        # Размещаем новую ставку
        auction['current_bid'] = bid_amount
        auction['highest_bidder'] = user_id
        user_balance[user_id] -= bid_amount
        
        # Сохраняем информацию о ставке
        if auction_id not in user_bids:
            user_bids[auction_id] = {}
        user_bids[auction_id][user_id] = bid_amount
        
        save_data()
        
        await message.reply(
            f"✅ <b>СТАВКА РАЗМЕЩЕНА!</b>\n\n"
            f"🚗 Аукцион: {auction['car']['name']}\n"
            f"💰 Ваша ставка: {format_money(bid_amount)}\n"
            f"💳 Спиcано с баланса: {format_money(bid_amount)}\n\n"
            f"🏆 Теперь вы лидируете в этом аукционе!",
            parse_mode='HTML'
        )
        
    except ValueError:
        await message.reply("❌ Неверный формат суммы!")
    except Exception as e:
        await message.reply("❌ Ошибка при размещении ставки!")

# ========== СИСТЕМА ПРОМОКОДОВ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['промокод', 'промо']))
async def promocode_command(message: types.Message):
    user_id = message.from_user.id
    
    if 'создать' in message.text.lower() and user_id == OWNER_ID:
        await create_promocode_command(message)
        return
    elif 'удалить' in message.text.lower() and user_id == OWNER_ID:
        await delete_promocode_command(message)
        return
    elif len(message.text.split()) >= 2:
        await use_promocode(message)
        return
    
    await show_promocode_info(message)

async def show_promocode_info(message: types.Message):
    """Показать информацию о промокодах"""
    text = "🎁 <b>СИСТЕМА ПРОМОКОДОВ</b>\n\n"
    
    if not promocodes:
        text += "❌ Активных промокодов нет.\n\n"
    else:
        text += "📋 <b>Активные промокоды:</b>\n"
        for code, data in promocodes.items():
            uses_left = data['max_uses'] - data['used_count']
            text += f"• <code>{code}</code> - {data['reward']:,}$ (осталось: {uses_left})\n"
        text += "\n"
    
    text += (
        "💡 <b>Использование:</b>\n"
        "• <code>промокод [КОД]</code> - активировать промокод\n"
    )
    
    if message.from_user.id == OWNER_ID:
        text += (
            "• <code>промокод создать [КОД] [СУММА] [ИСПОЛЬЗОВАНИЙ]</code> - создать промокод\n"
            "• <code>промокод удалить [КОД]</code> - удалить промокод\n"
        )
    
    await message.reply(text, parse_mode='HTML')

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('промокод создать') and m.from_user.id == OWNER_ID)
async def create_promocode_command(message: types.Message):
    """Создание промокода (только для админа)"""
    try:
        parts = message.text.split(' ')
        if len(parts) < 5:
            await message.reply("❌ Использование: промокод создать [КОД] [СУММА] [ИСПОЛЬЗОВАНИЙ]")
            return
        
        code = parts[2].upper()
        reward = int(parts[3])
        max_uses = int(parts[4])
        
        if code in promocodes:
            await message.reply("❌ Этот промокод уже существует!")
            return
        
        if reward <= 0 or max_uses <= 0:
            await message.reply("❌ Сумма и количество использований должны быть положительными!")
            return
        
        promocodes[code] = {
            'reward': reward,
            'max_uses': max_uses,
            'used_count': 0,
            'created_by': message.from_user.id,
            'created_at': time.time()
        }
        
        save_data()
        
        await message.reply(
            f"✅ <b>ПРОМОКОД СОЗДАН!</b>\n\n"
            f"🎁 Код: <code>{code}</code>\n"
            f"💰 Награда: {format_money(reward)}\n"
            f"📊 Макс. использований: {max_uses}",
            parse_mode='HTML'
        )
        
    except ValueError:
        await message.reply("❌ Неверный формат суммы или количества использований!")
    except Exception as e:
        await message.reply("❌ Ошибка при создании промокода!")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('промокод удалить') and m.from_user.id == OWNER_ID)
async def delete_promocode_command(message: types.Message):
    """Удаление промокода (только для админа)"""
    try:
        parts = message.text.split(' ')
        if len(parts) < 3:
            await message.reply("❌ Использование: промокод удалить [КОД]")
            return
        
        code = parts[2].upper()
        
        if code not in promocodes:
            await message.reply("❌ Промокод не найден!")
            return
        
        del promocodes[code]
        save_data()
        
        await message.reply(f"✅ Промокод <code>{code}</code> удален!", parse_mode='HTML')
        
    except Exception as e:
        await message.reply("❌ Ошибка при удалении промокода!")

async def use_promocode(message: types.Message):
    """Активация промокода"""
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            await message.reply("❌ Использование: промокод [КОД]")
            return
        
        code = parts[1].upper()
        
        if code not in promocodes:
            await message.reply("❌ Промокод не найден!")
            return
        
        promocode = promocodes[code]
        
        # Проверяем, не использовал ли пользователь уже этот промокод
        if user_id not in used_promocodes:
            used_promocodes[user_id] = []
        
        if code in used_promocodes[user_id]:
            await message.reply("❌ Вы уже использовали этот промокод!")
            return
        
        # Проверяем, не исчерпан ли лимит использований
        if promocode['used_count'] >= promocode['max_uses']:
            await message.reply("❌ Лимит использований этого промокода исчерпан!")
            return
        
        # Выдаем награду
        reward = promocode['reward']
        user_balance[user_id] += reward
        promocode['used_count'] += 1
        used_promocodes[user_id].append(code)
        
        # Если лимит исчерпан, удаляем промокод
        if promocode['used_count'] >= promocode['max_uses']:
            del promocodes[code]
        
        save_data()
        
        await message.reply(
            f"🎉 <b>ПРОМОКОД АКТИВИРОВАН!</b>\n\n"
            f"💰 Вы получили: {format_money(reward)}\n"
            f"💳 Ваш баланс: {format_money(user_balance[user_id])}",
            parse_mode='HTML'
        )
        
    except Exception as e:
        await message.reply("❌ Ошибка при активации промокода!")


@dp.message_handler(lambda m: m.text and m.text.lower().startswith('подписка ') and m.from_user.id == OWNER_ID)
async def admin_manage_subscription(message: types.Message):
    """Админские команды для подписок: setchannel, выдать, revoke, info"""
    parts = message.text.strip().split()
    cmd = parts[1].lower() if len(parts) > 1 else None
    try:
        if cmd == 'setchannel' and len(parts) > 2:
            global SUBS_CHANNEL_ID
            SUBS_CHANNEL_ID = parts[2]
            save_data()
            await message.reply(f"✅ Канал подписки установлен: {SUBS_CHANNEL_ID}")
            return

        if cmd in ('выдать', 'grant') and len(parts) >= 3:
            uid = int(parts[2])
            days = int(parts[3]) if len(parts) >= 4 else None
            grant_subscription(uid, days, 'manual')
            await message.reply(f"✅ Подписка выдана {uid} {'на ' + str(days) + ' дн.' if days else 'навсегда'}")
            return

        if cmd in ('revoke', 'удалить', 'отменить') and len(parts) >= 3:
            uid = int(parts[2])
            revoke_subscription(uid)
            await message.reply(f"✅ Подписка для {uid} отменена")
            return

        if cmd in ('info', 'посмотреть'):
            if len(parts) >= 3:
                uid = int(parts[2])
            else:
                uid = message.from_user.id
            sub = user_subscriptions.get(uid)
            if not sub:
                await message.reply(f"❌ У пользователя {uid} нет локальной подписки")
                return
            expires = sub.get('expires_at')
            expires_text = 'навсегда' if not expires else datetime.fromtimestamp(expires).strftime('%d.%m.%Y %H:%M')
            await message.reply(f"✅ Подписка у {uid}: {expires_text} (тип: {sub.get('type')})")
            return

    except Exception as e:
        await message.reply(f"❌ Ошибка команды подписки: {e}")


@dp.message_handler(lambda m: m.text and is_command_message(m, ['моя подписка', 'подписка инфо', 'подписка статус']))
async def my_subscription_info(message: types.Message):
    user_id = message.from_user.id
    try:
        local = user_subscriptions.get(user_id)
        local_ok = False
        if local:
            expires = local.get('expires_at')
            if not expires or time.time() < expires:
                local_ok = True
            else:
                local_ok = False

        channel_ok = False
        if SUBS_CHANNEL_ID:
            try:
                member = await bot.get_chat_member(SUBS_CHANNEL_ID, user_id)
                channel_ok = member and member.status not in ['left', 'kicked']
            except Exception:
                channel_ok = False

        if local_ok or channel_ok:
            await message.reply("✅ У вас активная подписка!")
        else:
            await message.reply("❌ У вас нет активной подписки. Чтобы подписаться — следуйте инструкциям администратора или подпишитесь на канал.")
    except Exception as e:
        await message.reply(f"❌ Не удалось проверить подписку: {e}")


@dp.message_handler(lambda m: m.text and is_command_message(m, ['подписчики', 'подписчики экспорт', 'subscribers', 'subscribers export']) and m.from_user.id == OWNER_ID)
async def admin_list_subscribers(message: types.Message):
    """Admin command: list or export subscribers"""
    text = "📋 <b>ПОДПИСЧИКИ</b>\n\n"
    subs = []
    for uid, info in user_subscriptions.items():
        expires = info.get('expires_at')
        expires_text = 'навсегда' if not expires else datetime.fromtimestamp(expires).strftime('%d.%m.%Y %H:%M')
        subs.append({'uid': uid, 'expires': expires, 'expires_text': expires_text, 'type': info.get('type')})
        text += f"• {uid} — {expires_text} (type: {info.get('type')})\n"

    await message.reply(text, parse_mode='HTML')

    # If export requested
    if message.text.strip().lower().startswith('подписчики экспорт') or message.text.strip().lower().startswith('subscribers export'):
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            path = os.path.join('backups', f'subscribers_{ts}.csv')
            os.makedirs('backups', exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write('user_id,expires_at,expires_date,type\n')
                for s in subs:
                    e_ts = '' if not s['expires'] else str(int(s['expires']))
                    f.write(f"{s['uid']},{e_ts},{s['expires_text']},{s['type']}\n")
            await bot.send_document(message.chat.id, open(path, 'rb'))
        except Exception as e:
            await message.reply(f"❌ Ошибка экспорта: {e}")

# ========== СИСТЕМА РОЗЫГРЫШЕЙ ==========

@dp.message_handler(lambda m: m.text and m.text.lower() == 'создать рз' and m.from_user.id == OWNER_ID)
async def create_giveaway_start(message: types.Message):
    """Начало создания розыгрыша (только админ)"""
    await message.reply(
        "🎉 <b>СОЗДАНИЕ РОЗЫГРЫША</b>\n\n"
        "Отправьте сообщение в формате:\n\n"
        "<code>текст: [описание]\n"
        "призы: [список призов через запятую]\n"
        "мест: [количество победителей]\n"
        "минбаланс: [минимальный баланс для участия]\n"
        "часов: [длительность в часах]</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>текст: Розыгрыш крутых машин!\n"
        "призы: Bugatti Chiron, Ferrari LaFerrari, Lamborghini Sian\n"
        "мест: 3\n"
        "минбаланс: 100000\n"
        "часов: 24</code>",
        parse_mode='HTML'
    )

@dp.message_handler(lambda m: m.text and 'текст:' in m.text.lower() and 'призы:' in m.text.lower() and m.from_user.id == OWNER_ID)
async def create_giveaway_config(message: types.Message):
    """Создание розыгрыша с конфигурацией"""
    global active_giveaway, giveaway_participants
    
    try:
        lines = message.text.split('\n')
        config = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                config[key] = value
        
        if 'текст' not in config or 'призы' not in config:
            await message.reply("❌ Обязательные поля: текст и призы")
            return
        
        description = config.get('текст', '')
        prizes_str = config.get('призы', '')
        prizes = [p.strip() for p in prizes_str.split(',')]
        winner_count = int(config.get('мест', len(prizes)))
        min_balance = int(config.get('минбаланс', 0))
        hours = int(config.get('часов', 24))
        
        active_giveaway = {
            'description': description,
            'prizes': prizes,
            'winner_count': winner_count,
            'min_balance': min_balance,
            'end_time': time.time() + (hours * 3600),
            'created_at': time.time(),
            'active': True
        }
        
        giveaway_participants = {}
        save_data()
        
        # Красивое сообщение о розыгрыше
        giveaway_text = format_giveaway_text(active_giveaway)
        
        await message.reply(giveaway_text, parse_mode='HTML')
        
    except ValueError as e:
        await message.reply(f"❌ Ошибка в формате чисел! {e}")
    except Exception as e:
        await message.reply(f"❌ Ошибка при создании розыгрыша: {e}")

@dp.message_handler(lambda m: m.text and is_command_message(m, ['+рз', '+ рз', 'рз']))
async def join_giveaway(message: types.Message):
    """Регистрация на участие в розыгрыше"""
    user_id = message.from_user.id
    ensure_user_initialized(user_id)
    
    if not is_giveaway_active():
        await message.reply("❌ В данный момент нет активных розыгрышей!")
        return
    
    # Проверка времени
    # time checked in is_giveaway_active
    
    # Проверка минимального баланса
    min_balance = active_giveaway.get('min_balance', 0)
    if user_balance.get(user_id, 0) < min_balance:
        await message.reply(f"❌ Недостаточный баланс! Минимум: {format_money(min_balance)}")
        return
    
    # Проверка на повторную регистрацию
    if user_id in giveaway_participants:
        await message.reply("❌ Вы уже зарегистрированы в розыгрыше!")
        return
    
    # Регистрируем участника
    add_giveaway_participant(user_id)
    # Пометим пользователя как ожидающего уточнения
    pending_giveaway_clarify[user_id] = True
    
    await message.reply(
        f"✅ <b>ВЫ ЗАРЕГИСТРИРОВАНЫ!</b>\n\n"
        f"🎉 Розыгрыш: {active_giveaway['description']}\n"
        f"👥 Участников: {len(giveaway_participants)}\n"
        f"🏆 Призов: {active_giveaway['winner_count']}\n\n"
        f"🍀 Удачи!",
        parse_mode='HTML'
    )

    await message.reply("💬 Пожалуйста, отправьте ответ на вопрос для уточнения (ник/комментарий). Отправьте 'пропустить' чтобы пропустить.")

@dp.message_handler(lambda m: m.text and is_command_message(m, ['розыгрыш', 'рз инфо']))
async def giveaway_info(message: types.Message):
    """Информация о текущем розыгрыше"""
    if not is_giveaway_active():
        await message.reply("❌ В данный момент нет активных розыгрышей!")
        return
    
    time_left = active_giveaway['end_time'] - time.time()
    
    if time_left <= 0:
        await message.reply("🎉 Розыгрыш завершен! Ожидайте результатов...")
        return
    
    hours = int(time_left // 3600)
    minutes = int((time_left % 3600) // 60)
    
    text = format_giveaway_text(active_giveaway)
    # Добавляем текущее состояние
    text = text.replace('💡 Для участия', f'👥 Участников: {len(giveaway_participants)}\n🏆 Победителей: {active_giveaway["winner_count"]}\n💰 Мин. баланс: {format_money(active_giveaway.get("min_balance", 0))}\n\n💡 Для участия')
    text += f"\n⏰ Осталось: {hours}ч {minutes}м"
    
    await message.reply(text, parse_mode='HTML')


@dp.message_handler(lambda m: m.text and m.from_user.id in pending_giveaway_clarify)
async def giveaway_clarify_handler(message: types.Message):
    """Handle clarifying question response when a user registers for a giveaway"""
    user_id = message.from_user.id
    if user_id not in pending_giveaway_clarify:
        return

    answer = message.text.strip()
    if answer.lower() == 'пропустить' or answer.lower() == 'skip':
        answer = None

    if user_id in giveaway_participants:
        giveaway_participants[user_id]['note'] = answer
        save_data()

    pending_giveaway_clarify.pop(user_id, None)
    await message.reply("✅ Спасибо! Ваша информация сохранена для розыгрыша.")

@dp.message_handler(lambda m: m.text and m.text.lower() == 'завершить рз' and m.from_user.id == OWNER_ID)
async def finish_giveaway_manual(message: types.Message):
    """Ручное завершение розыгрыша (только админ)"""
    if not is_giveaway_active():
        await message.reply("❌ Нет активных розыгрышей!")
        return
    
    await finish_giveaway()
    await message.reply("✅ Розыгрыш завершен вручную!")

async def finish_giveaway():
    """Автоматическое завершение розыгрыша"""
    global active_giveaway, giveaway_participants
    
    if not is_giveaway_active() or not giveaway_participants:
        return
    
    # Выбираем победителей
    winner_count = min(active_giveaway['winner_count'], len(giveaway_participants))
    winners = random.sample(list(giveaway_participants.keys()), winner_count)
    
    # Отправляем результаты
    result_text = (
        f"🎉 <b>РОЗЫГРЫШ ЗАВЕРШЕН!</b> 🎉\n\n"
        f"📝 {active_giveaway['description']}\n\n"
        f"🏆 <b>ПОБЕДИТЕЛИ:</b>\n\n"
    )
    
    for i, winner_id in enumerate(winners):
        try:
            winner = await bot.get_chat(winner_id)
            winner_name = f"@{winner.username}" if winner.username else winner.first_name
        except:
            winner_name = f"ID {winner_id}"
        
        prize = active_giveaway['prizes'][i] if i < len(active_giveaway['prizes']) else "Приз"
        note = giveaway_participants.get(winner_id, {}).get('note')
        note_text = f" ({note})" if note else ""
        result_text += f"{i+1} место: {winner_name}{note_text}\n🎁 Приз: {prize}\n\n"
        
        # Выдаем приз
        try:
            # Проверяем, это машина или деньги
            if prize.isdigit():
                # Это деньги
                user_balance[winner_id] = user_balance.get(winner_id, 0) + int(prize)
            else:
                # Это машина
                car_data = generate_car_data(prize, 'Эксклюзивные', winner_id)
                if winner_id not in user_garage:
                    user_garage[winner_id] = []
                user_garage[winner_id].append(car_data)
            
            # Уведомляем победителя
            await bot.send_message(
                winner_id,
                f"🎉 <b>ПОЗДРАВЛЯЕМ!</b> 🎉\n\n"
                f"Вы заняли {i+1} место в розыгрыше!\n"
                f"🎁 Ваш приз: <b>{prize}</b>\n\n"
                f"Приз добавлен в ваш гараж/баланс!",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Ошибка выдачи приза {winner_id}: {e}")
    
    result_text += f"👥 Всего участников: {len(giveaway_participants)}"
    
    # Отправляем результаты владельцу
    try:
        await bot.send_message(OWNER_ID, result_text, parse_mode='HTML')
    except:
        pass
    
    # Очищаем розыгрыш
    active_giveaway.clear()
    giveaway_participants.clear()
    save_data()

# ========== КОМАНДА ВОССТАНОВЛЕНИЯ ==========
@dp.message_handler(lambda m: m.text and is_command_message(m, ['список backup', 'список бекап', 'выбрать backup', 'все backup']) and m.from_user.id == OWNER_ID)
async def show_backup_list_command(message: types.Message):
    """Команда для показа списка backup"""
    await show_backup_list(message)

async def show_backup_list(message: types.Message, page: int = 0, edit_message: dict = None):
    """Показать список backup файлов с пагинацией"""
    backup_files = glob.glob('backups/bot_data_*.bak')
    
    if not backup_files:
        text = "❌ Backup файлы не найдены!"
        if edit_message:
            await bot.edit_message_text(
                chat_id=edit_message['chat_id'],
                message_id=edit_message['message_id'],
                text=text,
                parse_mode='HTML'
            )
        else:
            await message.reply(text)
        return
    
    # Сортируем файлы по дате изменения (новые сначала)
    backup_files.sort(key=os.path.getmtime, reverse=True)
    
    # Пагинация
    items_per_page = 5
    total_pages = (len(backup_files) + items_per_page - 1) // items_per_page
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(backup_files))
    
    text = f"📁 <b>СПИСОК BACKUP ФАЙЛОВ</b> (страница {page + 1}/{total_pages})\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    for i in range(start_idx, end_idx):
        backup_file = backup_files[i]
        try:
            file_time = os.path.getmtime(backup_file)
            file_date = datetime.fromtimestamp(file_time).strftime('%d.%m.%Y %H:%M:%S')
            
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            owner_balance = int(data.get('user_balance', {}).get(str(OWNER_ID), 0))
            owner_cars = len(data.get('user_garage', {}).get(str(OWNER_ID), []))
            total_cars = sum(len(garage) for garage in data.get('user_garage', {}).values())
            total_users = len(data.get('user_balance', {}))
            
            text += f"<b>{i+1}. {file_date}</b>\n"
            text += f"   💰 Баланс: {format_money(owner_balance)}\n"
            text += f"   🚗 Машины: {owner_cars}\n"
            text += f"   👥 Пользователей: {total_users}\n"
            text += f"   🏎️ Всего машин: {total_cars}\n\n"
            
            kb.add(types.InlineKeyboardButton(
                text=f"📅 {i+1}. {file_date.split()[0]}",
                callback_data=f"restore_backup:{backup_file}"
            ))
            
        except Exception as e:
            text += f"<b>{i+1}. Ошибка чтения файла</b>\n\n"
            kb.add(types.InlineKeyboardButton(
                text=f"❌ {i+1}. Ошибка",
                callback_data=f"backup_error:{i+1}"
            ))
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"backup_page:{page-1}"))
    
    nav_buttons.append(types.InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="backup_page_current"))
    
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="Вперед ➡️", callback_data=f"backup_page:{page+1}"))
    
    if nav_buttons:
        kb.row(*nav_buttons)
    
    # Дополнительные кнопки
    kb.row(
        types.InlineKeyboardButton(text="📅 Поиск по дате", callback_data="search_by_date"),
        types.InlineKeyboardButton(text="🔄 Восстановить последний", callback_data="restore_latest_backup")
    )
    
    if edit_message:
        await bot.edit_message_text(
            chat_id=edit_message['chat_id'],
            message_id=edit_message['message_id'],
            text=text,
            parse_mode='HTML',
            reply_markup=kb
        )
    else:
        await message.reply(text, parse_mode='HTML', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "backup_page_current")
async def backup_page_current(callback_query: types.CallbackQuery):
    """Текущая страница - ничего не делаем"""
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('backup_error:'))
async def backup_error_handler(callback_query: types.CallbackQuery):
    """Обработчик ошибок backup"""
    await bot.answer_callback_query(callback_query.id, "❌ Этот backup файл поврежден или недоступен!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('backup_page:'))
async def backup_page_navigation(callback_query: types.CallbackQuery):
    """Навигация по страницам backup"""
    await bot.answer_callback_query(callback_query.id)
    
    page = int(callback_query.data.split(':')[1])
    await show_backup_list(
        callback_query.message, 
        page, 
        edit_message={
            'chat_id': callback_query.message.chat.id,
            'message_id': callback_query.message.message_id
        }
    )

@dp.callback_query_handler(lambda c: c.data == "restore_latest_backup")
async def restore_latest_backup(callback_query: types.CallbackQuery):
    """Восстановление из самого нового backup"""
    await bot.answer_callback_query(callback_query.id)
    
    backup_file = find_latest_backup()
    if not backup_file:
        await bot.answer_callback_query(callback_query.id, "❌ Backup файлы не найдены!", show_alert=True)
        return
    
    # Показываем информацию о backup
    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        file_time = os.path.getmtime(backup_file)
        file_date = datetime.fromtimestamp(file_time).strftime('%d.%m.%Y %H:%M:%S')
        owner_balance = int(data.get('user_balance', {}).get(str(OWNER_ID), 0))
        owner_cars = len(data.get('user_garage', {}).get(str(OWNER_ID), []))
        total_cars = sum(len(garage) for garage in data.get('user_garage', {}).values())
        total_users = len(data.get('user_balance', {}))
        
        text = (
            f"📋 <b>ПОДТВЕРЖДЕНИЕ ВОССТАНОВЛЕНИЯ</b>\n\n"
            f"📁 Самый новый backup: <code>{os.path.basename(backup_file)}</code>\n"
            f"📅 Создан: {file_date}\n"
            f"💰 Ваш баланс: {format_money(owner_balance)}\n"
            f"🚗 Ваши машины: {owner_cars}\n"
            f"👥 Пользователей: {total_users}\n"
            f"🏎️ Всего машин: {total_cars}\n\n"
            f"⚠️ <b>Текущие данные будут заменены!</b>\n"
            f"Вы уверены что хотите восстановить этот backup?"
        )
        
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton(text="✅ Да, восстановить", callback_data=f"confirm_restore:{backup_file}"),
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="backup_page:0")
        )
        
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            parse_mode='HTML',
            reply_markup=kb
        )
        
    except Exception as e:
        await bot.answer_callback_query(callback_query.id, f"❌ Ошибка чтения backup: {e}", show_alert=True)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('confirm_restore:'))
async def confirm_restore_backup(callback_query: types.CallbackQuery):
    """Подтверждение восстановления из backup"""
    await bot.answer_callback_query(callback_query.id)
    
    backup_file = callback_query.data.split(':', 1)[1]
    
    if not os.path.exists(backup_file):
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="❌ Backup файл не найден!",
            parse_mode='HTML'
        )
        return
    
    # Восстанавливаем данные
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="🔄 <b>Восстанавливаю данные из backup...</b>",
        parse_mode='HTML'
    )
    
    if restore_from_backup(backup_file):
        save_data()
        
        total_cars = sum(len(garage) for garage in user_garage.values())
        total_money = sum(user_balance.values())
        owner_balance = user_balance.get(OWNER_ID, 0)
        
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=(
                f"✅ <b>ДАННЫЕ УСПЕШНО ВОССТАНОВЛЕНЫ!</b>\n\n"
                f"📊 <b>Статистика после восстановления:</b>\n"
                f"💰 Ваш баланс: {format_money(owner_balance)}\n"
                f"👥 Пользователей: {len(user_balance)}\n"
                f"🚗 Всего машин: {total_cars}\n"
                f"💵 Общий баланс: {format_money(total_money)}\n\n"
                f"💾 Backup файл: <code>{os.path.basename(backup_file)}</code>"
            ),
            parse_mode='HTML'
        )
    else:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="❌ <b>Ошибка при восстановлении данных!</b>",
            parse_mode='HTML'
        )

@dp.callback_query_handler(lambda c: c.data == "search_by_date")
async def search_by_date(callback_query: types.CallbackQuery):
    """Поиск backup по дате"""
    await bot.answer_callback_query(callback_query.id)
    
    backup_files = glob.glob('backups/bot_data_*.bak')
    if not backup_files:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="❌ Backup файлы не найдены!",
            parse_mode='HTML'
        )
        return
    
    # Группируем backup'ы по датам
    backups_by_date = {}
    for backup_file in backup_files:
        try:
            file_time = os.path.getmtime(backup_file)
            file_date = datetime.fromtimestamp(file_time).strftime('%Y-%m-%d')
            
            if file_date not in backups_by_date:
                backups_by_date[file_date] = []
            backups_by_date[file_date].append(backup_file)
        except:
            continue
    
    # Сортируем даты (новые сначала)
    sorted_dates = sorted(backups_by_date.keys(), reverse=True)
    
    text = "📅 <b>ВЫБЕРИТЕ ДАТУ</b>\n\n"
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    for date in sorted_dates[:20]:  # Показываем последние 20 дат
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d.%m.%Y')
        backup_count = len(backups_by_date[date])
        
        text += f"• {formatted_date} - {backup_count} backup\n"
        
        kb.add(types.InlineKeyboardButton(
            text=f"📅 {formatted_date} ({backup_count})",
            callback_data=f"backup_date:{date}"
        ))
    
    kb.add(types.InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="backup_page:0"))
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML',
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('backup_date:'))
async def show_backups_by_date(callback_query: types.CallbackQuery):
    """Показать backup'ы за конкретную дату"""
    await bot.answer_callback_query(callback_query.id)
    
    selected_date = callback_query.data.split(':')[1]
    backup_files = glob.glob('backups/bot_data_*.bak')
    
    # Фильтруем backup'ы по выбранной дате
    date_backups = []
    for backup_file in backup_files:
        try:
            file_time = os.path.getmtime(backup_file)
            file_date = datetime.fromtimestamp(file_time).strftime('%Y-%m-%d')
            
            if file_date == selected_date:
                date_backups.append(backup_file)
        except:
            continue
    
    # Сортируем по времени (сначала старые)
    date_backups.sort(key=os.path.getmtime)
    
    if not date_backups:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="❌ Не найдено backup за выбранную дату!",
            parse_mode='HTML'
        )
        return
    
    text = f"📅 <b>BACKUP ФАЙЛЫ ЗА {datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    for i, backup_file in enumerate(date_backups):
        try:
            file_time = os.path.getmtime(backup_file)
            file_time_str = datetime.fromtimestamp(file_time).strftime('%H:%M')
            
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            owner_balance = int(data.get('user_balance', {}).get(str(OWNER_ID), 0))
            owner_cars = len(data.get('user_garage', {}).get(str(OWNER_ID), []))
            
            text += f"<b>{i+1}. {file_time_str}</b>\n"
            text += f"   💰 Баланс: {format_money(owner_balance)}\n"
            text += f"   🚗 Машины: {owner_cars}\n\n"
            
            kb.add(types.InlineKeyboardButton(
                text=f"{i+1}. {file_time_str}",
                callback_data=f"restore_backup:{backup_file}"
            ))
            
        except Exception as e:
            text += f"<b>{i+1}. Ошибка чтения</b>\n\n"
            kb.add(types.InlineKeyboardButton(
                text=f"❌ {i+1}. Ошибка",
                callback_data=f"backup_error:{i+1}"
            ))
    
    kb.add(types.InlineKeyboardButton(text="⬅️ Назад к датам", callback_data="search_by_date"))
    
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='HTML',
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('restore_backup:'))
async def restore_selected_backup(callback_query: types.CallbackQuery):
    """Восстановление из выбранного backup"""
    await bot.answer_callback_query(callback_query.id)
    
    backup_file = callback_query.data.split(':', 1)[1]
    
    if not os.path.exists(backup_file):
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="❌ Backup файл не найден!",
            parse_mode='HTML'
        )
        return
    
    # Показываем информацию о выбранном backup
    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        file_time = os.path.getmtime(backup_file)
        file_date = datetime.fromtimestamp(file_time).strftime('%d.%m.%Y %H:%M:%S')
        owner_balance = int(data.get('user_balance', {}).get(str(OWNER_ID), 0))
        owner_cars = len(data.get('user_garage', {}).get(str(OWNER_ID), []))
        total_cars = sum(len(garage) for garage in data.get('user_garage', {}).values())
        total_users = len(data.get('user_balance', {}))
        
        text = (
            f"📋 <b>ПОДТВЕРЖДЕНИЕ ВОССТАНОВЛЕНИЯ</b>\n\n"
            f"📁 Backup: <code>{os.path.basename(backup_file)}</code>\n"
            f"📅 Создан: {file_date}\n"
            f"💰 Ваш баланс: {format_money(owner_balance)}\n"
            f"🚗 Ваши машины: {owner_cars}\n"
            f"👥 Пользователей: {total_users}\n"
            f"🏎️ Всего машин: {total_cars}\n\n"
            f"⚠️ <b>Текущие данные будут заменены!</b>\n"
            f"Вы уверены что хотите восстановить этот backup?"
        )
        
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton(text="✅ Да, восстановить", callback_data=f"confirm_restore:{backup_file}"),
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="backup_page:0")
        )
        
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            parse_mode='HTML',
            reply_markup=kb
        )
        
    except Exception as e:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"❌ Ошибка чтения backup файла: {e}",
            parse_mode='HTML'
        )

@dp.message_handler(lambda m: m.text and is_command_message(m, ['восстановить', 'рестор', 'restore']) and m.from_user.id == OWNER_ID)
async def restore_backup_command(message: types.Message):
    """Команда для восстановления данных из backup (только для владельца)"""
    await message.reply("🔄 <b>Поиск самого нового backup...</b>", parse_mode='HTML')
    
    backup_file = find_latest_backup()
    
    if not backup_file:
        await message.reply("❌ Backup файлы не найдены!")
        return
    
    await message.reply(f"📁 <b>Найден backup:</b> {os.path.basename(backup_file)}\n\nВосстанавливаю данные...", parse_mode='HTML')
    
    if restore_from_backup(backup_file):
        save_data()
        
        total_cars = sum(len(garage) for garage in user_garage.values())
        total_money = sum(user_balance.values())
        
        await message.reply(
            f"✅ <b>ДАННЫЕ УСПЕШНО ВОССТАНОВЛЕНЫ!</b>\n\n"
            f"📊 <b>Статистика после восстановления:</b>\n"
            f"👥 Пользователей: {len(user_balance)}\n"
            f"🚗 Всего машин: {total_cars}\n"
            f"💰 Общий баланс: {format_money(total_money)}\n\n"
            f"💾 Backup файл: <code>{os.path.basename(backup_file)}</code>",
            parse_mode='HTML'
        )
    else:
        await message.reply("❌ <b>Ошибка при восстановлении данных!</b>", parse_mode='HTML')


@dp.message_handler(lambda m: m.text and is_command_message(m, ['вайп']) and m.from_user.id == OWNER_ID)
async def wipe_command(message: types.Message):
    """Wipe all users (ask for confirmation)"""
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(text="✅ Подтвердить вайп", callback_data="confirm_wipe"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wipe")
    )
    await message.reply("⚠️ <b>ВНИМАНИЕ!</b> Все балансы, гаражи и т.д. пользователей будут удалены (кроме владельца). Подтвердить?", parse_mode='HTML', reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == 'confirm_wipe')
async def confirm_wipe_callback(callback_query: types.CallbackQuery):
    """Execute wipe (owner only)"""
    if callback_query.from_user.id != OWNER_ID:
        await bot.answer_callback_query(callback_query.id, "❌ Только владелец может подтверждать вайп", show_alert=True)
        return
    try:
        # Backup current data first
        create_backup()
        # Wipe data for all non-owner users
        for uid in list(user_balance.keys()):
            if uid == OWNER_ID:
                continue
            user_balance[uid] = 0
            user_garage[uid] = []
            user_shop_limits[uid] = {'count': 0, 'last_reset': datetime.now()}
            user_scrap[uid] = 0
            # remove from car_owner_map any cars that belong to this user
            for car_id, owner_id in list(car_owner_map.items()):
                if owner_id == uid:
                    del car_owner_map[car_id]

        # Clear bids and auction participation
        for auction_id, auction in list(auctions.items()):
            auction['participants'] = []
            auction['bids'] = {}

        # Clear user_bids per item
        for k, v in list(user_bids.items()):
            user_bids[k] = {}

        # Clear flea market entries owned by non-owners
        for offer_id, offer in list(flea_market.items()):
            if offer.get('owner_id') != OWNER_ID:
                del flea_market[offer_id]

        # Remove subscriptions for non-owner users
        for uid in list(user_subscriptions.keys()):
            if uid != OWNER_ID:
                del user_subscriptions[uid]

        save_data()
        await bot.edit_message_text(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, text="✅ Вайп выполнен. Все данные пользователей (кроме владельца) очищены.")
    except Exception as e:
        await bot.edit_message_text(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, text=f"❌ Ошибка при вайпе: {e}")

@dp.callback_query_handler(lambda c: c.data == 'cancel_wipe')
async def cancel_wipe_callback(callback_query: types.CallbackQuery):
    await bot.edit_message_text(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, text="❌ Вайп отменён.")

# ========== КОМАНДА СОБЫТИЯ ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['событие', 'ивент', 'event']))
async def event_info(message: types.Message):
    """Информация о текущем событии"""
    check_current_event()
    
    if current_event:
        event_data = EVENTS[current_event]
        days_left = (event_end_date - datetime.now()).days
        
        text = (
            f"{event_data['theme_color']} <b>{event_data['name']}</b>\n\n"
            f"📅 Действует до: {event_end_date.strftime('%d.%m.%Y')}\n"
            f"⏰ Осталось дней: {days_left}\n\n"
            f"🎁 <b>Бонусы события:</b>\n"
            f"• Множитель шанса: x{event_data['bonus_multiplier']}\n"
            f"• Специальные машины: {len(event_data['special_cars'])}\n\n"
            f"💡 {event_data['bonus_message']}\n\n"
        )
        
        text += f"🚗 <b>Специальные машины:</b>\n"
        for car in event_data['special_cars']:
            text += f"• {car}\n"
            
    else:
        text = (
            "📅 <b>ТЕКУЩИЕ СОБЫТИЯ</b>\n\n"
            "❌ В данный момент нет активных событий.\n\n"
            "🎁 <b>Ближайшие события:</b>\n"
            "• 🎃 Хэллоуин: 25 октября - 2 ноября\n"
            "• 🎄 Новый год: 20 декабря - 10 января\n"
            "• ☀️ Летнее безумие: 15 июня - 31 августа\n\n"
            "💡 Следите за обновлениями!"
        )
    
    await message.reply(text, parse_mode='HTML')

# ========== ПОМОЩЬ И СТАРТ ==========

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    is_owner = user_id == OWNER_ID
    
    check_current_event()
    event_message = get_event_message()
    
    decorations = get_event_decorations()
    
    text = (
        f"{decorations['main_emoji']} <b>Добро пожаловать в Авто-Бот!</b>\n\n"
    )
    
    if event_message:
        text += f"{event_message}\n\n"
    
    text += (
        "Здесь вы можете собирать коллекцию крутых машин, участвовать в гонках и улучшать свой гараж!\n\n"
        "💡 <b>Основные команды:</b>\n"
        "• <b>машина</b> - получить бесплатную машину\n"
        "• <b>гараж</b> - посмотреть свои машины\n"
        "• <b>магазин</b> - купить машину\n"
        "• <b>баланс</b> - проверить баланс\n"
        "• <b>профиль</b> - ваша статистика\n"
        "• <b>крафт</b> - создать машину из 2+ машин\n"
        "• <b>подписка</b> - управление подпиской / статус подписки\n"
        "• <b>событие</b> - информация о текущем событии\n"
    )
    
    if is_owner:
        text += "\n👑 <b>У вас есть доступ к админ командам!</b>"
    
    text += "\n\nНапишите <b>помощь</b> для полного списка команд!"
    
    await message.reply(text, parse_mode='HTML')

@dp.message_handler(lambda m: m.text and is_command_message(m, ['помощь', 'help', 'команды']))
async def help_command(message: types.Message):
    user_id = message.from_user.id
    is_owner = user_id == OWNER_ID
    
    decorations = get_event_decorations()
    
    text = (
        f"{decorations['main_emoji']} <b>АВТО-БОТ - КОМАНДЫ</b>\n\n"
        "🎯 <b>Основные команды:</b>\n"
        "• <b>машина</b> - получить бесплатную машину\n"
        "• <b>гараж</b> - посмотреть свои машины\n"
        "• <b>магазин</b> - купить машину\n"
        "• <b>баланс</b> - проверить баланс\n"
        "• <b>профиль</b> - ваша статистика\n\n"
        "🎮 <b>Дополнительные команды:</b>\n"
        "• <b>бонус</b> - ежедневный подарок\n"
        "• <b>топ</b> - лучшие игроки\n"
        "• <b>статистика</b> - статистика сервера\n"
        "• <b>квесты</b> - ежедневные задания\n"
        "• <b>достижения</b> - ваши достижения\n"
        "• <b>тюнинг</b> - улучшить машину\n"
        "• <b>гонка</b> - участвовать в гонках\n"
        "• <b>обмен</b> - обменяться машинами\n"
        "• <b>крафт</b> - создать машину из 2+ машин\n"
        "• <b>аукцион</b> - список аукционов\n"
        "• <b>подписка</b> - управление подпиской / статус подписки\n"
        "• <b>ставка [ID] [сумма]</b> - сделать ставку\n"
        "• <b>промокод [КОД]</b> - активировать промокод\n"
        "• <b>событие</b> - информация о текущем событии\n"
    )
    
    if is_owner:
        text += "\n👑 <b>АДМИН КОМАНДЫ:</b>\n"
        text += "• <b>/рассылка [текст]</b> - отправить сообщение всем\n"
        text += "• <b>эксклюзив</b> - получить эксклюзивную машину\n"
        text += "• <b>деньги [сумма] [ID]</b> - выдать деньги\n"
        text += "• <b>сброс кд</b> - сбросить кулдаун\n"
        text += "• <b>удалить машину [ID]</b> - удалить машину\n"
        text += "• <b>промокод</b> - управление промокодами\n"
        text += "• <b>промокод создать</b> - создать промокод\n"
        text += "• <b>промокод удалить</b> - удалить промокод\n"
        text += "• <b>аукцион создать</b> - создать аукцион\n"
        text += "• <b>восстановить</b> - восстановить данные из backup\n"
        text += "• <b>подписка setchannel</b> - задать канал подписки (админ)\n"
        text += "• <b>подписка выдать [ID] [дни]</b> - выдать подписку пользователю (админ)\n"
        text += "• <b>подписка revoke [ID]</b> - отозвать подписку (админ)\n"
        text += "• <b>подписка info [ID]</b> - информация о подписке пользователя (админ)\n"
    
    text += "\n💡 <i>Просто напишите команду в чат!</i>"
    
    await message.reply(text, parse_mode='HTML')
    # ДОБАВЬ ПЕРЕД periodic_checks:
async def finish_auction(auction_id):
    """Завершение аукциона"""
    print(f"🔨 Аукцион {auction_id} завершен")

# ========== ПЕРИОДИЧЕСКИЕ ПРОВЕРКИ С ИЗНОСОМ ==========

async def periodic_checks():
    """Периодические проверки (аукционы, лотерея, износ и т.д.)"""
    while True:
        try:
            # Проверяем текущее событие каждый час
            check_current_event()
            
            # Проверяем аукционы
            current_time = time.time()
            expired_auctions = []
            
            for auction_id, auction in auctions.items():
                if current_time > auction['end_time']:
                    expired_auctions.append(auction_id)
            
            # ЗАКОММЕНТИРУЙ ЭТИ 2 СТРОКИ:
                for auction_id in expired_auctions:
                 await finish_auction(auction_id)
            
            # Удаляем старые предложения с барахолки (старше 7 дней)
            expired_flea = []
            for offer_id, offer in flea_market.items():
                if current_time - offer['created_at'] > 7 * 24 * 60 * 60:
                    expired_flea.append(offer_id)
            
            for offer_id in expired_flea:
                del flea_market[offer_id]
            
            # Удаляем просроченные обмены
            expired_trades = []
            for trade_id, trade in trade_offers.items():
                if current_time - trade['created_at'] > 30 * 60:  # 30 минут
                    expired_trades.append(trade_id)
            
            for trade_id in expired_trades:
                del trade_offers[trade_id]
            
            # Проверяем розыгрыши
            if is_giveaway_active() and current_time > active_giveaway.get('end_time', 0):
                await finish_giveaway()
            
            await asyncio.sleep(30)  # Проверяем каждые 30 секунд
            
        except Exception as e:
            print(f"Ошибка в periodic_checks: {e}")
            await asyncio.sleep(30)

# ========== ЗАПУСК БОТА ==========

async def on_startup(dp): 
    # Проверяем текущее событие при запуске
    check_current_event()
    
    # Загружаем обычные данные сначала
    load_data() 
    init_crafting_system()
    
    # Затем принудительное восстановление данных ЕСЛИ НУЖНО
    await force_restore_if_needed()
    
    try: 
        if os.path.isdir(IMAGE_BASE_PATH): 
            files = [f for f in os.listdir(IMAGE_BASE_PATH) if os.path.isfile(os.path.join(IMAGE_BASE_PATH, f))] 
            print(f"Найдено файлов в папке images: {len(files)}")
            
            for rarity, models in cars.items(): 
                for model in models: 
                    found_file = None
                    for file in files:
                        file_lower = file.lower()
                        model_lower = model.lower().replace(' ', '_').replace('-', '_')
                        
                        if model_lower in file_lower or any(word in file_lower for word in model_lower.split()):
                            found_file = file
                            break
                    
                    if found_file:
                        CAR_FILE_MAPPING[model] = found_file
            
            for uid, garage in user_garage.items():
                for car in garage:
                    car_name = car.get('name')
                    if car_name in CAR_FILE_MAPPING:
                        car['image_path'] = IMAGE_BASE_PATH + CAR_FILE_MAPPING[car_name]
        else: 
            os.makedirs(IMAGE_BASE_PATH, exist_ok=True) 
    except Exception as e: 
        print('Image mapping error:', e) 
        # ========== КОМАНДА ПРИНУДИТЕЛЬНОГО ВОССТАНОВЛЕНИЯ БАЛАНСА ==========

@dp.message_handler(lambda m: m.text and is_command_message(m, ['восстановить баланс', 'рестор баланс']) and m.from_user.id == OWNER_ID)
async def force_restore_balance(message: types.Message):
    """Принудительное восстановление из backup с лучшим балансом"""
    await message.reply("🔄 <b>Принудительное восстановление баланса...</b>", parse_mode='HTML')
    await force_restore_if_needed()
    
    total_cars = sum(len(garage) for garage in user_garage.values())
    total_money = sum(user_balance.values())
    owner_balance = user_balance.get(OWNER_ID, 0)
    
    await message.reply(
        f"✅ <b>Восстановление завершено!</b>\n\n"
        f"💰 Баланс владельца: {format_money(owner_balance)}\n"
        f"🚗 Всего машин: {total_cars}\n"
        f"💵 Общий баланс: {format_money(total_money)}",
        parse_mode='HTML'
    )

async def on_shutdown(dp):
    save_data()
    print('Данные сохранены при выключении')

# ========== ЗАПУСК БОТА ==========

async def on_startup(dp):
    # Проверяем текущее событие при запуске
    check_current_event()
    
    # Загружаем обычные данные сначала
    load_data() 
    init_crafting_system()
    
    # Затем принудительное восстановление данных ЕСЛИ НУЖНО
    await force_restore_if_needed()
    
    try: 
        if os.path.isdir(IMAGE_BASE_PATH): 
            files = [f for f in os.listdir(IMAGE_BASE_PATH) if os.path.isfile(os.path.join(IMAGE_BASE_PATH, f))] 
            print(f"Найдено файлов в папке images: {len(files)}")
            
            for rarity, models in cars.items(): 
                for model in models: 
                    found_file = None
                    for file in files:
                        file_lower = file.lower()
                        model_lower = model.lower().replace(' ', '_').replace('-', '_')
                        
                        if model_lower in file_lower or any(word in file_lower for word in model_lower.split()):
                            found_file = file
                            break
                    
                    if found_file:
                        CAR_FILE_MAPPING[model] = found_file
            
            for uid, garage in user_garage.items():
                for car in garage:
                    car_name = car.get('name')
                    if car_name in CAR_FILE_MAPPING:
                        car['image_path'] = IMAGE_BASE_PATH + CAR_FILE_MAPPING[car_name]
        else: 
            os.makedirs(IMAGE_BASE_PATH, exist_ok=True) 
    except Exception as e: 
        print('Image mapping error:', e) 

    print('Бот запущен') 
    print(f'Активное событие: {current_event}')

if __name__=='__main__': 
    try: 
        asyncio.get_event_loop() 
    except RuntimeError: 
        asyncio.set_event_loop(asyncio.new_event_loop()) 
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)
    async def handle_health_check(request):
        return web.Response(text="OK")

if __name__ == '__main__':
    asyncio.get_event_loop()    
    # Логика для asyncio (переносим сюда)
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    # 1. Создаем приложение aiohttp
    app = web.Application()
    # 2. Добавляем маршрут для проверки здоровья
    app.router.add_get('/health', handle_health_check)
    
    # 3. Запускаем Polling И веб-сервер вместе! (только ОДИН раз)
    executor.start_polling(
        dp, 
        skip_updates=True, 
        on_startup=on_startup, 
        on_shutdown=on_shutdown,
        web_app=app, 
        web_app_port=8000
    )
