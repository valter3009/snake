"""
Сбор новостей из Telegram каналов через Telethon
"""
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
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
            # Путь к файлу сессии в data директории (монтируется из Docker)
            data_dir = Path(__file__).parent.parent.parent / "data"
            data_dir.mkdir(exist_ok=True)
            session_path = data_dir / self.session_name

            self.client = TelegramClient(str(session_path), self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            logger.info(f"✅ Подключено к Telegram (сессия: {session_path}.session)")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Telegram: {e}")
            raise

    async def disconnect(self):
        """Отключиться от Telegram"""
        if self.client:
            await self.client.disconnect()
            logger.info("👋 Отключено от Telegram")

    async def _download_media(
        self,
        message: Message,
        channel_username: str
    ) -> Optional[str]:
        """
        Скачать медиа файл из сообщения

        Args:
            message: Telegram сообщение
            channel_username: Username канала

        Returns:
            Путь к скачанному файлу или None
        """
        try:
            if not (message.photo or message.video):
                return None

            # Создаем директорию для медиа
            data_dir = Path(__file__).parent.parent.parent / "data" / "media"
            data_dir.mkdir(parents=True, exist_ok=True)

            # Генерируем уникальное имя файла
            media_type = "photo" if message.photo else "video"
            timestamp = int(message.date.timestamp())
            hash_input = f"{channel_username}_{message.id}_{timestamp}"
            file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]

            # Определяем расширение
            extension = ".jpg" if message.photo else ".mp4"
            filename = f"{media_type}_{file_hash}{extension}"
            file_path = data_dir / filename

            # Скачиваем медиа
            logger.info(f"  📥 Скачивание {media_type} из @{channel_username}/{message.id}...")
            await self.client.download_media(message, file=str(file_path))

            logger.info(f"  ✅ Медиа сохранено: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.warning(f"  ⚠️ Ошибка скачивания медиа: {e}")
            return None

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

            # Скачиваем медиа если есть
            media_path = None
            has_media = message.photo is not None or message.video is not None

            if has_media:
                media_path = await self._download_media(message, channel_username)

            news_item = {
                'title': title,
                'url': url,
                'description': description,
                'published_at': published_at,
                'source': f"@{channel_username}",
                'is_international': False,  # Все каналы российские
                'telegram_message_id': message.id,
                'has_media': has_media,
                'media_path': media_path,  # Локальный путь к медиа файлу
                'media_type': 'photo' if message.photo else ('video' if message.video else None)
            }

            return news_item

        except Exception as e:
            logger.warning(f"⚠️ Ошибка преобразования сообщения: {e}")
            return None
