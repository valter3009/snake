"""
Конфигурация бота из переменных окружения
"""
import os
import logging
import pytz
from typing import Optional
from dotenv import load_dotenv

# Загружаем .env если есть (для локальной разработки)
load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Конфигурация приложения"""

    def __init__(self):
        # Telegram (ОБЯЗАТЕЛЬНЫЕ)
        self.TELEGRAM_BOT_TOKEN: str = self._get_required("TELEGRAM_BOT_TOKEN")
        self.TELEGRAM_ADMIN_ID: int = int(self._get_required("TELEGRAM_ADMIN_ID"))
        self.TELEGRAM_CHANNEL_ID: str = self._get_required("TELEGRAM_CHANNEL_ID")

        # Claude AI (ОБЯЗАТЕЛЬНЫЙ)
        self.ANTHROPIC_API_KEY: str = self._get_required("ANTHROPIC_API_KEY")

        # Telegram Client API (ОБЯЗАТЕЛЬНЫЕ для парсинга каналов)
        self.TELEGRAM_API_ID: int = int(self._get_required("TELEGRAM_API_ID"))
        self.TELEGRAM_API_HASH: str = self._get_required("TELEGRAM_API_HASH")
        self.TELEGRAM_PHONE: str = self._get_required("TELEGRAM_PHONE")

        # Database (ОБЯЗАТЕЛЬНЫЙ)
        self.DATABASE_URL: str = self._get_required("DATABASE_URL")

        # Настройки (с дефолтами)
        self.TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "Europe/Moscow"))
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

        # Расписание публикаций
        self.MIN_POSTS_PER_DAY: int = int(os.getenv("MIN_POSTS_PER_DAY", "40"))
        self.MAX_POSTS_PER_DAY: int = int(os.getenv("MAX_POSTS_PER_DAY", "50"))
        self.PUBLISH_START_HOUR: int = int(os.getenv("PUBLISH_START_HOUR", "7"))
        self.PUBLISH_END_HOUR: int = int(os.getenv("PUBLISH_END_HOUR", "23"))

        # Контент
        self.TOP_NEWS_COUNT: int = int(os.getenv("TOP_NEWS_COUNT", "5"))
        self.NEWS_MAX_AGE_HOURS: int = int(os.getenv("NEWS_MAX_AGE_HOURS", "6"))
        self.MIN_COLLECTION_INTERVAL: int = int(os.getenv("MIN_COLLECTION_INTERVAL", "10"))
        self.MAX_COLLECTION_INTERVAL: int = int(os.getenv("MAX_COLLECTION_INTERVAL", "20"))

        # Разное
        self.POSTS_RETENTION_DAYS: int = int(os.getenv("POSTS_RETENTION_DAYS", "30"))
        self.MODERATION_TIMEOUT: int = int(os.getenv("MODERATION_TIMEOUT", "600"))

        logger.info("✅ Конфигурация успешно загружена")
        self._log_config()

    def _get_required(self, key: str) -> str:
        """Получить обязательную переменную окружения"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"❌ Обязательная переменная {key} не найдена!")
        return value

    def _log_config(self):
        """Логирование конфигурации (без секретов)"""
        logger.info("📊 Текущая конфигурация:")
        logger.info(f"  • Канал для публикации: {self.TELEGRAM_CHANNEL_ID}")
        logger.info(f"  • Telegram для парсинга: {self.TELEGRAM_PHONE}")
        logger.info(f"  • Посты/день: {self.MIN_POSTS_PER_DAY}-{self.MAX_POSTS_PER_DAY}")
        logger.info(f"  • Время: {self.PUBLISH_START_HOUR}:00-{self.PUBLISH_END_HOUR}:00 МСК")
        logger.info(f"  • Топ новостей: {self.TOP_NEWS_COUNT}")
        logger.info(f"  • База данных: {'✅ подключена' if self.DATABASE_URL else '❌ не настроена'}")


# Глобальный объект конфигурации
config: Optional[Config] = None


def init_config() -> Config:
    """Инициализация глобальной конфигурации"""
    global config
    config = Config()
    return config


def get_config() -> Optional[Config]:
    """Получить глобальную конфигурацию"""
    return config
