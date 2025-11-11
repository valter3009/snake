"""
Конфигурация бота
"""
import os
from dataclasses import dataclass
from typing import List
import pytz

# Загружаем .env только для локальной разработки (если файл существует)
try:
    from dotenv import load_dotenv
    if os.path.exists('.env'):
        load_dotenv()
except ImportError:
    # python-dotenv не установлен (например, на Railway)
    pass


@dataclass
class Config:
    """Основная конфигурация приложения"""

    # Telegram настройки
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHANNEL_ID: str
    TELEGRAM_ADMIN_ID: int

    # API ключи
    ANTHROPIC_API_KEY: str
    NEWS_API_KEY: str

    # База данных
    DATABASE_URL: str

    # RSS ленты
    RSS_FEEDS: List[str] = None

    # NewsAPI настройки
    NEWS_API_LANGUAGES: List[str] = None
    NEWS_API_CATEGORIES: List[str] = None

    # Временные настройки
    TIMEZONE: pytz.timezone = pytz.timezone('Europe/Moscow')
    PUBLISH_START_HOUR: int = 7  # 7:00 МСК
    PUBLISH_END_HOUR: int = 23   # 23:00 МСК

    # Настройки публикации
    MIN_POSTS_PER_DAY: int = 4
    MAX_POSTS_PER_DAY: int = 10

    # Интервалы сбора новостей (в минутах)
    MIN_COLLECTION_INTERVAL: int = 30
    MAX_COLLECTION_INTERVAL: int = 60

    # Настройки модерации
    MODERATION_TIMEOUT: int = 15 * 60  # 15 минут в секундах

    # Время хранения опубликованных постов в БД (дни)
    POSTS_RETENTION_DAYS: int = 30

    # Возраст новостей для сбора (часов)
    NEWS_MAX_AGE_HOURS: int = 6

    # Порог схожести для определения дубликатов (%)
    DUPLICATE_THRESHOLD: int = 70

    # Количество топовых новостей для публикации за цикл
    TOP_NEWS_COUNT: int = 3

    # Тематический баланс (проценты)
    TOPIC_BALANCE: dict = None

    # Географический баланс (проценты)
    GEO_BALANCE: dict = None

    def __post_init__(self):
        """Инициализация значений по умолчанию"""
        if self.RSS_FEEDS is None:
            self.RSS_FEEDS = [
                'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
                'https://tass.ru/rss/v2.xml',
                'https://www.kommersant.ru/RSS/main.xml'
            ]

        if self.NEWS_API_LANGUAGES is None:
            self.NEWS_API_LANGUAGES = ['ru', 'en']

        if self.NEWS_API_CATEGORIES is None:
            self.NEWS_API_CATEGORIES = ['general', 'business', 'technology']

        if self.TOPIC_BALANCE is None:
            self.TOPIC_BALANCE = {
                'politics': 70,
                'economy': 15,
                'technology': 10,
                'society': 5
            }

        if self.GEO_BALANCE is None:
            self.GEO_BALANCE = {
                'russia': 60,
                'world': 30,
                'cis': 10
            }


def load_config() -> Config:
    """Загрузка конфигурации из переменных окружения"""

    # Проверка обязательных переменных
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHANNEL_ID',
        'TELEGRAM_ADMIN_ID',
        'ANTHROPIC_API_KEY',
        'NEWS_API_KEY',
        'DATABASE_URL'
    ]

    # Логируем статус каждой переменной
    print("=" * 60)
    print("ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ:")
    print("=" * 60)
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Маскируем значение для безопасности
            masked = value[:10] + "..." if len(value) > 10 else "***"
            print(f"✅ {var}: {masked}")
        else:
            print(f"❌ {var}: НЕ НАЙДЕНА")
    print("=" * 60)

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")

    return Config(
        TELEGRAM_BOT_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN'),
        TELEGRAM_CHANNEL_ID=os.getenv('TELEGRAM_CHANNEL_ID'),
        TELEGRAM_ADMIN_ID=int(os.getenv('TELEGRAM_ADMIN_ID')),
        ANTHROPIC_API_KEY=os.getenv('ANTHROPIC_API_KEY'),
        NEWS_API_KEY=os.getenv('NEWS_API_KEY'),
        DATABASE_URL=os.getenv('DATABASE_URL')
    )


# Глобальный объект конфигурации
config: Config = None


def init_config():
    """Инициализация глобальной конфигурации"""
    global config
    config = load_config()
    return config
