"""
Публикатор сообщений в Telegram канал.

Использует python-telegram-bot для отправки сообщений.
"""

from typing import Optional
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from config import config
from utils.logger import get_logger

logger = get_logger(__name__)


class TelegramPublisher:
    """
    Публикует сообщения в Telegram канал.

    Features:
    - Асинхронная отправка сообщений
    - Markdown форматирование
    - Обработка ошибок Telegram API
    - Retry при временных ошибках
    """

    def __init__(self):
        """Инициализирует Telegram бота."""
        self.bot = Bot(token=config.telegram.bot_token)
        self.channel_id = config.telegram.channel_id
        logger.info(f"TelegramPublisher инициализирован для канала: {self.channel_id}")

    async def send_message(
        self,
        text: str,
        parse_mode: str = ParseMode.MARKDOWN,
        max_retries: int = 3
    ) -> Optional[int]:
        """
        Отправляет сообщение в канал.

        Args:
            text: Текст сообщения
            parse_mode: Режим парсинга (MARKDOWN или HTML)
            max_retries: Количество попыток при ошибке

        Returns:
            int или None: ID отправленного сообщения или None при ошибке

        Example:
            >>> publisher = TelegramPublisher()
            >>> msg_id = await publisher.send_message("**Test** message")
            >>> msg_id is not None
            True
        """
        for attempt in range(max_retries):
            try:
                logger.debug(f"Отправка сообщения в {self.channel_id} (попытка {attempt + 1}/{max_retries})")

                # Отправляем сообщение
                message = await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=False
                )

                logger.info(f"✅ Сообщение отправлено (ID: {message.message_id})")
                return message.message_id

            except TelegramError as e:
                logger.error(f"Telegram API ошибка: {e}")

                # Если это rate limit или временная ошибка - повторяем
                if "Too Many Requests" in str(e) or "Bad Gateway" in str(e):
                    if attempt < max_retries - 1:
                        import asyncio
                        wait_time = (attempt + 1) * 5  # 5, 10, 15 секунд
                        logger.warning(f"Повтор через {wait_time}с...")
                        await asyncio.sleep(wait_time)
                        continue

                # Иначе возвращаем None
                logger.error(f"❌ Не удалось отправить сообщение после {max_retries} попыток")
                return None

            except Exception as e:
                logger.error(f"Неожиданная ошибка при отправке: {e}", exc_info=True)
                return None

        return None

    async def test_connection(self) -> bool:
        """
        Проверяет соединение с Telegram API.

        Returns:
            bool: True если соединение работает
        """
        try:
            bot_info = await self.bot.get_me()
            logger.info(f"✅ Подключение к Telegram успешно: @{bot_info.username}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Telegram: {e}")
            return False

    async def get_chat_info(self) -> Optional[dict]:
        """
        Получает информацию о канале.

        Returns:
            dict или None: Информация о канале
        """
        try:
            chat = await self.bot.get_chat(self.channel_id)
            return {
                'id': chat.id,
                'title': chat.title,
                'type': chat.type,
                'username': chat.username,
                'description': chat.description,
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале: {e}")
            return None

    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Экранирует специальные символы Markdown.

        Args:
            text: Исходный текст

        Returns:
            str: Экранированный текст
        """
        # Символы которые нужно экранировать в Markdown
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

        for char in special_chars:
            text = text.replace(char, f'\\{char}')

        return text
