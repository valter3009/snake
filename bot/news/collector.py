"""
Сбор новостей из Telegram каналов
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from bot.core.logger import get_logger
from bot.core.exceptions import NewsCollectionError
from bot.news.sources import TELEGRAM_CHANNELS
from bot.news.telegram_collector import TelegramNewsCollector

logger = get_logger(__name__)


class NewsCollector:
    """
    Сборщик новостей из Telegram каналов
    """

    def __init__(
        self,
        telegram_api_id: int,
        telegram_api_hash: str,
        telegram_phone: str,
        max_age_hours: int = 6
    ):
        """
        Инициализация сборщика новостей

        Args:
            telegram_api_id: Telegram API ID
            telegram_api_hash: Telegram API Hash
            telegram_phone: Номер телефона для Telegram
            max_age_hours: Максимальный возраст новостей в часах
        """
        self.max_age_hours = max_age_hours
        self.telegram_collector = TelegramNewsCollector(
            api_id=telegram_api_id,
            api_hash=telegram_api_hash,
            phone=telegram_phone,
            max_age_hours=max_age_hours
        )
        logger.info(f"🔧 NewsCollector инициализирован (max_age: {max_age_hours}ч)")

    async def collect_all_news(self) -> List[Dict[str, Any]]:
        """
        Собрать новости из всех источников

        Returns:
            Список новостей
        """
        logger.info("📰 Начинаю сбор новостей из Telegram каналов...")

        try:
            # Собираем из Telegram каналов
            telegram_news = await self.telegram_collector.collect_from_channels(
                channel_usernames=TELEGRAM_CHANNELS,
                limit=30  # По 30 сообщений из каждого канала
            )

            logger.info(f"  • Telegram: собрано {len(telegram_news)} сообщений")

            # Удаляем дубликаты по URL
            unique_news = self._remove_duplicates(telegram_news)

            # Фильтруем по времени
            recent_news = self._filter_by_time(unique_news)

            # Подсчитываем статистику по источникам
            russian_count = sum(1 for n in recent_news if not n.get('is_international', False))
            international_count = sum(1 for n in recent_news if n.get('is_international', False))

            # Подсчитываем по каналам
            by_channel = {}
            for news in recent_news:
                source = news.get('source', 'Unknown')
                by_channel[source] = by_channel.get(source, 0) + 1

            logger.info(f"✅ Всего собрано уникальных свежих новостей: {len(recent_news)}")
            logger.info(f"  • Российские источники: {russian_count}")
            logger.info(f"  • Международные источники: {international_count}")
            for channel, count in by_channel.items():
                logger.info(f"  • {channel}: {count}")

            return recent_news

        except Exception as e:
            logger.error(f"❌ Ошибка при сборе новостей: {e}")
            return []

    async def close(self):
        """Закрыть соединения"""
        await self.telegram_collector.disconnect()

    async def download_media(
        self,
        channel_username: str,
        message_id: int
    ) -> Optional[str]:
        """
        Скачать медиа для конкретного сообщения

        Args:
            channel_username: Username канала
            message_id: ID сообщения

        Returns:
            Путь к скачанному файлу или None
        """
        return await self.telegram_collector.download_media_for_message(
            channel_username, message_id
        )

    def _remove_duplicates(self, news: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Удалить дубликаты по URL

        Args:
            news: Список новостей

        Returns:
            Список уникальных новостей
        """
        seen_urls = set()
        unique_news = []

        for item in news:
            url = item.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_news.append(item)

        return unique_news

    def _filter_by_time(self, news: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Отфильтровать новости по времени публикации

        Args:
            news: Список новостей

        Returns:
            Список свежих новостей
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.max_age_hours)
        recent_news = []

        for item in news:
            published_at = item.get('published_at')
            if published_at:
                # Убеждаемся что дата имеет timezone
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)

                if published_at > cutoff_time:
                    recent_news.append(item)

        return recent_news
