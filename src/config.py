"""
Конфигурация бота - все настройки в одном месте.

Загружает переменные окружения и предоставляет их через классы конфигурации.
"""

import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()


@dataclass
class TelegramConfig:
    """Настройки Telegram бота."""

    bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    channel_id: str = os.getenv('TELEGRAM_CHANNEL_ID', '')

    def validate(self) -> bool:
        """Проверяет что все обязательные параметры заданы."""
        return bool(self.bot_token and self.channel_id)


@dataclass
class ClaudeConfig:
    """Настройки Claude API."""

    api_key: str = os.getenv('ANTHROPIC_API_KEY', '')
    model: str = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
    max_tokens: int = int(os.getenv('CLAUDE_MAX_TOKENS', '1200'))
    temperature: float = float(os.getenv('CLAUDE_TEMPERATURE', '0.7'))

    def validate(self) -> bool:
        """Проверяет что API ключ задан."""
        return bool(self.api_key)


@dataclass
class DatabaseConfig:
    """Настройки базы данных."""

    url: str = os.getenv('DATABASE_URL', 'sqlite:///./crypto_bot.db')

    # Railway автоматически предоставляет DATABASE_URL для PostgreSQL
    # Для локальной разработки используется SQLite


@dataclass
class FilterConfig:
    """Настройки фильтрации событий."""

    # Минимальные пороги для публикации
    min_whale_amount: int = int(os.getenv('MIN_WHALE_AMOUNT', '5000000'))  # $5M
    min_listing_market_cap: int = int(os.getenv('MIN_LISTING_MARKET_CAP', '100000000'))  # $100M
    min_importance_score: int = int(os.getenv('MIN_IMPORTANCE_SCORE', '7'))  # 7/10

    # Индекс страха/жадности - минимальное изменение для публикации
    fear_greed_min_change: int = int(os.getenv('FEAR_GREED_MIN_CHANGE', '10'))  # 10 пунктов


@dataclass
class ScheduleConfig:
    """Настройки интервалов проверок и расписания."""

    # Интервалы проверок в минутах
    whale_check_interval: int = int(os.getenv('WHALE_CHECK_INTERVAL', '10'))
    listings_check_interval: int = int(os.getenv('LISTINGS_CHECK_INTERVAL', '15'))
    fear_greed_check_interval: int = int(os.getenv('FEAR_GREED_CHECK_INTERVAL', '60'))
    airdrop_check_interval: int = int(os.getenv('AIRDROP_CHECK_INTERVAL', '360'))
    news_check_interval: int = int(os.getenv('NEWS_CHECK_INTERVAL', '30'))

    # Время рыночных обзоров (UTC)
    market_overview_times: List[str] = None

    def __post_init__(self):
        """Парсит время рыночных обзоров из переменной окружения."""
        times_str = os.getenv('MARKET_OVERVIEW_TIMES', '08:00,20:00')
        self.market_overview_times = [t.strip() for t in times_str.split(',')]


@dataclass
class RateLimitConfig:
    """Настройки лимитов публикаций."""

    max_messages_per_hour: int = int(os.getenv('MAX_MESSAGES_PER_HOUR', '3'))
    max_messages_per_day: int = int(os.getenv('MAX_MESSAGES_PER_DAY', '12'))
    min_interval_seconds: int = int(os.getenv('MIN_INTERVAL_SECONDS', '600'))  # 10 минут


@dataclass
class LogConfig:
    """Настройки логирования."""

    level: str = os.getenv('LOG_LEVEL', 'INFO')
    log_dir: str = os.getenv('LOG_DIR', './logs')


class Config:
    """
    Главный класс конфигурации - объединяет все настройки.

    Example:
        >>> config = Config()
        >>> if config.validate():
        ...     print("Конфигурация валидна!")
    """

    def __init__(self):
        self.telegram = TelegramConfig()
        self.claude = ClaudeConfig()
        self.database = DatabaseConfig()
        self.filters = FilterConfig()
        self.schedule = ScheduleConfig()
        self.rate_limit = RateLimitConfig()
        self.log = LogConfig()

        # Общие настройки
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.debug = os.getenv('DEBUG', 'False').lower() == 'true'

    def validate(self) -> bool:
        """
        Проверяет что все критичные настройки заданы.

        Returns:
            bool: True если конфигурация валидна, False иначе
        """
        if not self.telegram.validate():
            print("❌ Ошибка: TELEGRAM_BOT_TOKEN и TELEGRAM_CHANNEL_ID обязательны!")
            return False

        if not self.claude.validate():
            print("❌ Ошибка: ANTHROPIC_API_KEY обязателен!")
            return False

        return True

    def print_config(self):
        """Выводит текущую конфигурацию (без секретов)."""
        print("\n" + "=" * 60)
        print("📋 КОНФИГУРАЦИЯ БОТА")
        print("=" * 60)
        print(f"Окружение: {self.environment}")
        print(f"Debug режим: {self.debug}")
        print(f"\n🤖 Telegram:")
        print(f"  Канал: {self.telegram.channel_id}")
        print(f"  Токен: {'✅ Задан' if self.telegram.bot_token else '❌ Не задан'}")
        print(f"\n🧠 Claude API:")
        print(f"  Модель: {self.claude.model}")
        print(f"  API ключ: {'✅ Задан' if self.claude.api_key else '❌ Не задан'}")
        print(f"\n💾 База данных:")
        print(f"  URL: {self.database.url}")
        print(f"\n🔍 Фильтры:")
        print(f"  Мин. сумма китов: ${self.filters.min_whale_amount:,}")
        print(f"  Мин. market cap: ${self.filters.min_listing_market_cap:,}")
        print(f"  Мин. важность: {self.filters.min_importance_score}/10")
        print(f"\n⏰ Расписание:")
        print(f"  Проверка китов: каждые {self.schedule.whale_check_interval} мин")
        print(f"  Проверка листингов: каждые {self.schedule.listings_check_interval} мин")
        print(f"  Обзоры рынка: {', '.join(self.schedule.market_overview_times)} UTC")
        print(f"\n📊 Лимиты:")
        print(f"  Сообщений в час: {self.rate_limit.max_messages_per_hour}")
        print(f"  Сообщений в день: {self.rate_limit.max_messages_per_day}")
        print(f"  Мин. интервал: {self.rate_limit.min_interval_seconds}с")
        print("=" * 60 + "\n")


# Создаем глобальный экземпляр конфигурации
config = Config()
