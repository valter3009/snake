"""
Система модерации постов перед публикацией
"""
import asyncio
from typing import Optional, Dict, Any, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.core.logger import get_logger

logger = get_logger(__name__)


class PostModerator:
    """
    Модератор постов с возможностью подтверждения/отклонения
    """

    def __init__(self, admin_id: int, timeout: int = 900, publisher=None):
        """
        Инициализация модератора

        Args:
            admin_id: ID администратора в Telegram
            timeout: Таймаут ожидания решения (секунды)
            publisher: Публикатор для авто-публикации после таймаута
        """
        self.admin_id = admin_id
        self.timeout = timeout
        self.publisher = publisher
        self.pending_posts: Dict[str, Dict[str, Any]] = {}
        logger.info(f"🔧 PostModerator инициализирован (timeout: {timeout}с)")

    async def send_for_moderation(
        self,
        bot,
        post_content: str,
        news_item: Dict[str, Any],
        context: Optional[Any] = None
    ) -> str:
        """
        Отправить пост на модерацию администратору

        Args:
            bot: Telegram bot instance
            post_content: Контент поста
            news_item: Данные новости
            context: Контекст для callback

        Returns:
            ID поста в системе модерации
        """
        try:
            # Генерируем уникальный ID для поста
            post_id = f"mod_{len(self.pending_posts)}_{asyncio.get_event_loop().time()}"

            # Создаем клавиатуру для модерации
            keyboard = [
                [
                    InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve_{post_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{post_id}")
                ],
                [
                    InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{post_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Формируем сообщение для модератора
            title = news_item.get('title', 'Без заголовка')
            source = news_item.get('source', 'Неизвестный источник')
            url = news_item.get('url', '')
            image_url = news_item.get('image_url')
            video_url = news_item.get('video_url')

            # Индикатор медиа
            media_info = ""
            if video_url:
                media_info = "\n🎥 Видео: Да"
            elif image_url:
                media_info = "\n🖼️ Изображение: Да"

            moderation_message = f"""🔔 НОВЫЙ ПОСТ НА МОДЕРАЦИИ

Источник: {source}
Заголовок: {title}{media_info}

━━━━━━━━━━━━━━━━━━
{post_content}
━━━━━━━━━━━━━━━━━━

Оригинал: {url}"""

            # Отправляем администратору
            sent_message = await bot.send_message(
                chat_id=self.admin_id,
                text=moderation_message[:4000],  # Telegram limit
                reply_markup=reply_markup,
                parse_mode=None  # Отключаем parse_mode для избежания проблем
            )

            # Сохраняем в pending
            self.pending_posts[post_id] = {
                'content': post_content,
                'news_item': news_item,
                'message_id': sent_message.message_id,
                'status': 'pending',
                'context': context,
                'bot': bot
            }

            logger.info(f"📤 Пост отправлен на модерацию: {post_id}")

            # Запускаем задачу авто-одобрения в фоне
            asyncio.create_task(self._auto_approve_after_timeout(post_id))

            return post_id

        except Exception as e:
            logger.error(f"❌ Ошибка отправки на модерацию: {e}")
            raise

    async def handle_moderation_callback(
        self,
        query,
        bot
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Обработать callback от модератора

        Args:
            query: Callback query от Telegram
            bot: Telegram bot instance

        Returns:
            Tuple (action, post_data) где action in ['approve', 'reject', 'edit']
        """
        try:
            callback_data = query.data
            action, post_id = callback_data.split('_', 1)

            if post_id not in self.pending_posts:
                await query.answer("⚠️ Пост уже обработан или не найден")
                return ('unknown', None)

            post_data = self.pending_posts[post_id]

            if action == 'approve':
                post_data['status'] = 'approved'
                await query.answer("✅ Пост одобрен для публикации")
                await query.edit_message_reply_markup(reply_markup=None)
                logger.info(f"✅ Пост одобрен: {post_id}")

            elif action == 'reject':
                post_data['status'] = 'rejected'
                await query.answer("❌ Пост отклонен")
                await query.edit_message_reply_markup(reply_markup=None)
                logger.info(f"❌ Пост отклонен: {post_id}")

            elif action == 'edit':
                await query.answer("✏️ Функция редактирования в разработке")
                return ('edit', post_data)

            return (action, post_data)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки callback модерации: {e}")
            return ('error', None)

    def get_pending_count(self) -> int:
        """
        Получить количество постов на модерации

        Returns:
            Количество постов
        """
        return len([p for p in self.pending_posts.values() if p['status'] == 'pending'])

    def clear_post(self, post_id: str) -> None:
        """
        Удалить пост из системы модерации

        Args:
            post_id: ID поста
        """
        if post_id in self.pending_posts:
            del self.pending_posts[post_id]
            logger.info(f"🗑️ Пост удален из модерации: {post_id}")

    async def _auto_approve_after_timeout(self, post_id: str) -> bool:
        """
        Автоматически одобрить и опубликовать пост после таймаута

        Args:
            post_id: ID поста

        Returns:
            True если пост был авто-одобрен и опубликован
        """
        try:
            await asyncio.sleep(self.timeout)

            if post_id not in self.pending_posts:
                return False

            post_data = self.pending_posts[post_id]

            # Публикуем только если пост все еще на модерации
            if post_data['status'] == 'pending':
                post_data['status'] = 'auto_approved'
                logger.info(f"⏰ Пост авто-одобрен после таймаута ({self.timeout}с): {post_id}")

                # Публикуем пост
                if self.publisher:
                    try:
                        content = post_data.get('content', '')
                        news_item = post_data.get('news_item', {})
                        image_url = news_item.get('image_url')
                        video_url = news_item.get('video_url')
                        bot = post_data.get('bot')

                        # Публикуем с медиа если оно есть
                        if video_url or image_url:
                            message_id = await self.publisher.publish_with_media(
                                content, news_item,
                                photo_url=image_url,
                                video_url=video_url
                            )
                        else:
                            message_id = await self.publisher.publish_post(content, news_item)

                        if message_id:
                            media_text = " с видео" if video_url else (" с изображением" if image_url else "")
                            logger.info(f"✅ Пост{media_text} авто-опубликован (msg_id: {message_id})")

                            # Уведомляем админа
                            if bot:
                                await bot.send_message(
                                    chat_id=self.admin_id,
                                    text=f"⏰ Пост автоматически опубликован после {self.timeout // 60} минут ожидания\n\nID: {message_id}"
                                )

                            # Удаляем кнопки у сообщения модерации
                            try:
                                await bot.edit_message_reply_markup(
                                    chat_id=self.admin_id,
                                    message_id=post_data.get('message_id'),
                                    reply_markup=None
                                )
                            except:
                                pass

                            return True

                    except Exception as e:
                        logger.error(f"❌ Ошибка авто-публикации: {e}")
                        return False
                else:
                    logger.warning(f"⚠️ Publisher не настроен для авто-публикации")
                    return False

        except Exception as e:
            logger.error(f"❌ Ошибка в _auto_approve_after_timeout: {e}")
            return False

        return False
