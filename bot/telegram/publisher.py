"""
Публикация контента в Telegram канал
"""
from typing import Optional, Dict, Any
from pathlib import Path
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
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

            # Публикуем в канал (ссылка уже встроена в текст)
            message = await self.bot.send_message(
                chat_id=self.channel_id,
                text=content,
                parse_mode='Markdown',  # Включаем Markdown форматирование
                disable_web_page_preview=True  # Отключаем preview
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
        photo_url: Optional[str] = None,
        video_url: Optional[str] = None,
        photo_path: Optional[str] = None,
        video_path: Optional[str] = None
    ) -> Optional[int]:
        """
        Опубликовать пост с медиа

        Args:
            content: Контент поста
            news_item: Данные новости
            photo_url: URL изображения
            video_url: URL видео
            photo_path: Локальный путь к изображению
            video_path: Локальный путь к видео

        Returns:
            ID сообщения в Telegram или None при ошибке
        """
        try:
            # Приоритет: локальные файлы > URL
            video_source = video_path or video_url
            photo_source = photo_path or photo_url

            logger.info(f"📊 Медиа данные: video_path={video_path}, photo_path={photo_path}, video_url={video_url}, photo_url={photo_url}")

            if video_source:
                logger.info(f"🎥 Публикация поста с видео ({('файл: ' + str(video_path) if video_path else 'URL: ' + str(video_url))})...")

                if video_path:
                    # Локальный файл - проверяем существование
                    video_file_path = Path(video_path)
                    if not video_file_path.exists():
                        logger.error(f"❌ Видео файл не найден: {video_path}")
                        return await self.publish_post(content, news_item)

                    logger.info(f"📂 Открываю видео файл: {video_path} (размер: {video_file_path.stat().st_size} байт)")
                    with open(video_path, 'rb') as video_file:
                        message = await self.bot.send_video(
                            chat_id=self.channel_id,
                            video=video_file,
                            caption=content[:1024],  # Telegram caption limit
                            parse_mode='Markdown'
                        )
                else:
                    # URL
                    message = await self.bot.send_video(
                        chat_id=self.channel_id,
                        video=video_url,
                        caption=content[:1024],  # Telegram caption limit
                        parse_mode='Markdown'
                    )
            elif photo_source:
                logger.info(f"📷 Публикация поста с изображением ({('файл: ' + str(photo_path) if photo_path else 'URL: ' + str(photo_url))})...")

                if photo_path:
                    # Локальный файл - проверяем существование
                    photo_file_path = Path(photo_path)
                    if not photo_file_path.exists():
                        logger.error(f"❌ Фото файл не найден: {photo_path}")
                        return await self.publish_post(content, news_item)

                    logger.info(f"📂 Открываю фото файл: {photo_path} (размер: {photo_file_path.stat().st_size} байт)")
                    with open(photo_path, 'rb') as photo_file:
                        message = await self.bot.send_photo(
                            chat_id=self.channel_id,
                            photo=photo_file,
                            caption=content[:1024],  # Telegram caption limit
                            parse_mode='Markdown'
                        )
                else:
                    # URL
                    message = await self.bot.send_photo(
                        chat_id=self.channel_id,
                        photo=photo_url,
                        caption=content[:1024],  # Telegram caption limit
                        parse_mode='Markdown'
                    )
            else:
                # Публикуем как обычный текст
                logger.info("📝 Медиа не найдено, публикуем как текст")
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
