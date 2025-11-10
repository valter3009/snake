"""
Модуль для публикации постов в Telegram канал
"""

import logging
from typing import Optional, Dict
from io import BytesIO
from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logger = logging.getLogger(__name__)


class TelegramPublisher:
    """Класс для публикации в Telegram канал"""

    def __init__(self):
        """Инициализация Telegram бота"""
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")

        if not TELEGRAM_CHANNEL_ID:
            raise ValueError("TELEGRAM_CHANNEL_ID не установлен в переменных окружения")

        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.channel_id = TELEGRAM_CHANNEL_ID
        logger.info("Telegram Publisher инициализирован")

    async def publish_post(
        self,
        text: str,
        image_data: Optional[bytes] = None,
        image_format: Optional[str] = None
    ) -> Optional[int]:
        """
        Публикация поста в канал

        Args:
            text: Текст поста
            image_data: Байты изображения (опционально)
            image_format: Формат изображения (опционально)

        Returns:
            ID опубликованного сообщения или None
        """
        try:
            logger.info(f"Публикация поста в канал {self.channel_id}")

            # Публикация с изображением
            if image_data and image_format:
                message = await self._publish_with_image(text, image_data, image_format)
            else:
                # Публикация только текста
                message = await self._publish_text_only(text)

            if message:
                logger.info(f"Пост успешно опубликован, ID: {message.message_id}")
                return message.message_id
            else:
                logger.error("Не удалось опубликовать пост")
                return None

        except TelegramError as e:
            logger.error(f"Ошибка Telegram API: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при публикации: {e}")
            return None

    async def _publish_with_image(
        self,
        text: str,
        image_data: bytes,
        image_format: str
    ):
        """
        Публикация поста с изображением

        Args:
            text: Текст поста
            image_data: Байты изображения
            image_format: Формат изображения

        Returns:
            Объект сообщения или None
        """
        try:
            # Определение имени файла по формату
            filename = f"image.{image_format.lower()}"

            # Создание BytesIO объекта
            photo_file = BytesIO(image_data)
            photo_file.name = filename

            # Отправка фото с подписью
            message = await self.bot.send_photo(
                chat_id=self.channel_id,
                photo=photo_file,
                caption=text,
                parse_mode=None  # Используем обычный текст без разметки
            )

            return message

        except TelegramError as e:
            logger.error(f"Ошибка отправки фото: {e}")

            # Попытка отправить только текст, если фото не прошло
            logger.info("Пытаемся отправить только текст...")
            return await self._publish_text_only(text)

        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке фото: {e}")
            return None

    async def _publish_text_only(self, text: str):
        """
        Публикация только текста без изображения

        Args:
            text: Текст поста

        Returns:
            Объект сообщения или None
        """
        try:
            message = await self.bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode=None  # Используем обычный текст без разметки
            )

            return message

        except TelegramError as e:
            logger.error(f"Ошибка отправки текста: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке текста: {e}")
            return None

    async def test_connection(self) -> bool:
        """
        Тестирование подключения к Telegram

        Returns:
            True если подключение успешно
        """
        try:
            # Получение информации о боте
            bot_info = await self.bot.get_me()
            logger.info(f"Подключение успешно. Бот: @{bot_info.username}")

            # Попытка получить информацию о канале
            try:
                chat = await self.bot.get_chat(self.channel_id)
                logger.info(f"Канал найден: {chat.title if hasattr(chat, 'title') else self.channel_id}")
            except TelegramError as e:
                logger.warning(f"Не удалось получить информацию о канале: {e}")
                logger.warning("Убедитесь, что бот добавлен в канал как администратор")

            return True

        except TelegramError as e:
            logger.error(f"Ошибка подключения к Telegram: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при тестировании: {e}")
            return False

    async def get_channel_info(self) -> Optional[Dict]:
        """
        Получение информации о канале

        Returns:
            Словарь с информацией о канале или None
        """
        try:
            chat = await self.bot.get_chat(self.channel_id)

            info = {
                'id': chat.id,
                'title': getattr(chat, 'title', 'N/A'),
                'type': chat.type,
                'username': getattr(chat, 'username', None),
                'description': getattr(chat, 'description', None),
            }

            return info

        except TelegramError as e:
            logger.error(f"Ошибка получения информации о канале: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            return None
