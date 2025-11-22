"""
Сбор новостей из Telegram каналов через Telethon
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from telethon import TelegramClient
from telethon.tl.types import Message
from bot.core.logger import get_logger

logger = get_logger(__name__)


class TelegramNewsCollector:
    """
    Сборщик новостей из Telegram каналов
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_name: str = "news_collector",
        max_age_hours: int = 6
    ):
        """
        Инициализация сборщика

        Args:
            api_id: Telegram API ID (получить на my.telegram.org)
            api_hash: Telegram API Hash
            phone: Номер телефона для авторизации
            session_name: Имя сессии Telethon
            max_age_hours: Максимальный возраст новостей в часах
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.max_age_hours = max_age_hours
        self.client = None
        logger.info(f"🔧 TelegramNewsCollector инициализирован (max_age: {max_age_hours}ч)")

    async def connect(self):
        """Подключиться к Telegram"""
        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            logger.info("✅ Подключено к Telegram")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Telegram: {e}")
            raise

    async def disconnect(self):
        """Отключиться от Telegram"""
        if self.client:
            await self.client.disconnect()
            logger.info("👋 Отключено от Telegram")

    async def collect_from_channels(
        self,
        channel_usernames: List[str],
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Собрать сообщения из Telegram каналов

        Args:
            channel_usernames: Список @username каналов (например: ['dmitrynikotin', 'novosti_efir'])
            limit: Максимальное количество сообщений из каждого канала

        Returns:
            Список новостей
        """
        if not self.client:
            await self.connect()

        all_news = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.max_age_hours)

        for username in channel_usernames:
            try:
                logger.info(f"📱 Сбор из канала @{username}...")

                # Получаем сообщения из канала
                messages = []
                async for message in self.client.iter_messages(username, limit=limit):
                    if not isinstance(message, Message):
                        continue

                    # Пропускаем служебные сообщения
                    if not message.text:
                        continue

                    # Проверяем возраст сообщения
                    if message.date.replace(tzinfo=timezone.utc) < cutoff_time:
                        break  # Старые сообщения, дальше не идем

                    messages.append(message)

                # Преобразуем сообщения в формат новостей
                for msg in messages:
                    news_item = await self._message_to_news_item(msg, username)
                    if news_item:
                        all_news.append(news_item)

                logger.info(f"  ✅ @{username}: собрано {len(messages)} сообщений")

            except Exception as e:
                logger.warning(f"⚠️ Ошибка при сборе из @{username}: {e}")
                continue

        logger.info(f"✅ Всего собрано сообщений: {len(all_news)}")
        return all_news

    async def _message_to_news_item(
        self,
        message: Message,
        channel_username: str
    ) -> Optional[Dict[str, Any]]:
        """
        Преобразовать Telegram сообщение в новость

        Args:
            message: Telegram сообщение
            channel_username: Username канала

        Returns:
            Словарь с данными новости
        """
        try:
            # Формируем URL сообщения
            url = f"https://t.me/{channel_username}/{message.id}"

            # Получаем текст
            text = message.text or ""

            # Если текст слишком короткий, пропускаем
            if len(text) < 50:
                return None

            # Первые 100 символов как заголовок
            title = text[:100].replace('\n', ' ').strip()
            if len(title) == 100:
                title += "..."

            # Весь текст как описание
            description = text

            # Дата публикации
            published_at = message.date.replace(tzinfo=timezone.utc)

            news_item = {
                'title': title,
                'url': url,
                'description': description,
                'published_at': published_at,
                'source': f"@{channel_username}",
                'is_international': False,  # Все каналы российские
                'telegram_message_id': message.id,
                'has_media': message.photo is not None or message.video is not None
            }

            return news_item

        except Exception as e:
            logger.warning(f"⚠️ Ошибка преобразования сообщения: {e}")
            return None
