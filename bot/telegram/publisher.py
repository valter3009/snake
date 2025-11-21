"""
Публикация контента в Telegram канал
"""
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError
from bot.core.logger import get_logger
from bot.core.exceptions import PublishError
from bot.core.database import db_manager

logger = get_logger(__name__)


class ChannelPublisher:
    """
    Публикация постов в Telegram канал
    """

    def __init__(self, bot: Bot, channel_id: str):
        """
        Инициализация публикатора

        Args:
            bot: Telegram bot instance
            channel_id: ID или @username канала
        """
        self.bot = bot
        self.channel_id = channel_id
        logger.info(f"🔧 ChannelPublisher инициализирован (канал: {channel_id})")

    async def publish_post(
        self,
        content: str,
        news_item: Dict[str, Any],
        disable_preview: bool = False
    ) -> Optional[int]:
        """
        Опубликовать пост в канал

        Args:
            content: Контент поста
            news_item: Данные новости
            disable_preview: Отключить предпросмотр ссылок

        Returns:
            ID сообщения в Telegram или None при ошибке
        """
        try:
            logger.info(f"📤 Публикация поста в канал {self.channel_id}...")

            # Публикуем в канал
            message = await self.bot.send_message(
                chat_id=self.channel_id,
                text=content,
                parse_mode=None,  # Отключаем parse_mode
                disable_web_page_preview=disable_preview
            )

            logger.info(f"✅ Пост опубликован (message_id: {message.message_id})")

            # Сохраняем в базу данных (если доступна)
            if db_manager:
                url = news_item.get('url', '')
                title = news_item.get('title', '')
                published_at = news_item.get('published_at')
                source = news_item.get('source', '')

                await db_manager.add_published_post(
                    url=url,
                    title=title,
                    published_at=published_at,
                    source=source,
                    telegram_message_id=message.message_id
                )

            return message.message_id

        except TelegramError as e:
            logger.error(f"❌ Ошибка публикации в Telegram: {e}")
            raise PublishError(f"Не удалось опубликовать пост: {e}")

        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при публикации: {e}")
            return None

    async def publish_with_media(
        self,
        content: str,
        news_item: Dict[str, Any],
        photo_url: Optional[str] = None
    ) -> Optional[int]:
        """
        Опубликовать пост с медиа

        Args:
            content: Контент поста
            news_item: Данные новости
            photo_url: URL изображения

        Returns:
            ID сообщения в Telegram или None при ошибке
        """
        try:
            if photo_url:
                logger.info("📷 Публикация поста с изображением...")

                message = await self.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=photo_url,
                    caption=content[:1024],  # Telegram caption limit
                    parse_mode=None
                )
            else:
                # Публикуем как обычный текст
                return await self.publish_post(content, news_item)

            logger.info(f"✅ Пост с медиа опубликован (message_id: {message.message_id})")

            # Сохраняем в БД
            if db_manager:
                url = news_item.get('url', '')
                title = news_item.get('title', '')
                published_at = news_item.get('published_at')
                source = news_item.get('source', '')

                await db_manager.add_published_post(
                    url=url,
                    title=title,
                    published_at=published_at,
                    source=source,
                    telegram_message_id=message.message_id
                )

            return message.message_id

        except Exception as e:
            logger.error(f"❌ Ошибка публикации с медиа: {e}")
            # Fallback: публикуем без медиа
            return await self.publish_post(content, news_item)

    async def delete_post(self, message_id: int) -> bool:
        """
        Удалить пост из канала

        Args:
            message_id: ID сообщения

        Returns:
            True если удалено успешно
        """
        try:
            await self.bot.delete_message(
                chat_id=self.channel_id,
                message_id=message_id
            )

            logger.info(f"🗑️ Пост удален (message_id: {message_id})")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка удаления поста: {e}")
            return False

    async def edit_post(self, message_id: int, new_content: str) -> bool:
        """
        Редактировать опубликованный пост

        Args:
            message_id: ID сообщения
            new_content: Новый контент

        Returns:
            True если отредактировано успешно
        """
        try:
            await self.bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=message_id,
                text=new_content,
                parse_mode=None
            )

            logger.info(f"✏️ Пост отредактирован (message_id: {message_id})")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка редактирования поста: {e}")
            return False

    async def get_channel_info(self) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о канале

        Returns:
            Словарь с информацией о канале
        """
        try:
            chat = await self.bot.get_chat(self.channel_id)

            info = {
                'id': chat.id,
                'title': chat.title,
                'username': chat.username,
                'type': chat.type,
                'members_count': getattr(chat, 'members_count', None)
            }

            logger.info(f"📊 Информация о канале: {info['title']}")
            return info

        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о канале: {e}")
            return None
