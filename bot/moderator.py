"""
Модуль модерации постов
"""
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from io import BytesIO

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.error import TelegramError

import bot.config
from bot.post_generator import TelegramPost
from bot.media_handler import media_handler
from bot.database import db_manager

logger = logging.getLogger(__name__)


class ModerationResult:
    """Результат модерации"""

    def __init__(self, approved: bool, edited_text: Optional[str] = None):
        self.approved = approved
        self.edited_text = edited_text


class Moderator:
    """Модератор постов"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.pending_posts: Dict[int, Dict[str, Any]] = {}  # message_id -> {post, event, result}

    async def submit_for_moderation(self, post: TelegramPost) -> ModerationResult:
        """
        Отправка поста на модерацию админу

        Args:
            post: Пост для модерации

        Returns:
            ModerationResult с результатом модерации
        """
        logger.info("Отправляем пост на модерацию...")

        try:
            # Скачиваем и оптимизируем изображение если есть
            photo = None
            if post.image_url:
                photo = await media_handler.download_and_optimize_image(post.image_url)

            # Создаем клавиатуру с кнопками
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Опубликовать", callback_data="approve"),
                    InlineKeyboardButton("✏️ Редактировать", callback_data="edit"),
                ],
                [
                    InlineKeyboardButton("❌ Отклонить", callback_data="reject")
                ]
            ])

            # Отправляем сообщение админу
            if photo:
                message = await self.bot.send_photo(
                    chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
                    photo=photo,
                    caption=f"📝 **НОВЫЙ ПОСТ НА МОДЕРАЦИЮ**\n\n{post.text}\n\n_Источник: {post.source}_",
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            else:
                message = await self.bot.send_message(
                    chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
                    text=f"📝 **НОВЫЙ ПОСТ НА МОДЕРАЦИЮ**\n\n{post.text}\n\n_Источник: {post.source}_",
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )

            # Создаем event для ожидания решения
            moderation_event = asyncio.Event()
            moderation_result = {'approved': False, 'edited_text': None}

            # Сохраняем в словаре ожидающих постов
            self.pending_posts[message.message_id] = {
                'post': post,
                'event': moderation_event,
                'result': moderation_result
            }

            # Ожидаем решения с таймаутом
            try:
                await asyncio.wait_for(
                    moderation_event.wait(),
                    timeout=bot.config.config.MODERATION_TIMEOUT
                )
                logger.info("Получено решение модератора")
            except asyncio.TimeoutError:
                logger.info("Таймаут модерации - автоматическая публикация")
                moderation_result['approved'] = True

            # Удаляем из ожидающих
            self.pending_posts.pop(message.message_id, None)

            return ModerationResult(
                approved=moderation_result['approved'],
                edited_text=moderation_result.get('edited_text')
            )

        except Exception as e:
            logger.error(f"Ошибка при модерации: {e}")
            # В случае ошибки автоматически одобряем
            return ModerationResult(approved=True)

    async def handle_moderation_callback(self, query_data: str, message_id: int, user_id: int):
        """
        Обработка callback от кнопок модерации

        Args:
            query_data: Данные callback (approve/edit/reject)
            message_id: ID сообщения с постом
            user_id: ID пользователя
        """
        # Проверяем, что это админ
        if user_id != bot.config.config.TELEGRAM_ADMIN_ID:
            logger.warning(f"Попытка модерации от не-админа: {user_id}")
            return

        # Проверяем, есть ли пост в ожидании
        if message_id not in self.pending_posts:
            logger.warning(f"Пост {message_id} не найден в ожидающих")
            return

        pending = self.pending_posts[message_id]

        if query_data == "approve":
            logger.info("Пост одобрен модератором")
            pending['result']['approved'] = True
            pending['event'].set()

            # Обновляем сообщение
            try:
                await self.bot.edit_message_caption(
                    chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
                    message_id=message_id,
                    caption=f"{pending['post'].text}\n\n✅ **ОДОБРЕНО**",
                    parse_mode='Markdown'
                )
            except TelegramError:
                try:
                    await self.bot.edit_message_text(
                        chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
                        message_id=message_id,
                        text=f"{pending['post'].text}\n\n✅ **ОДОБРЕНО**",
                        parse_mode='Markdown'
                    )
                except TelegramError as e:
                    logger.error(f"Не удалось обновить сообщение: {e}")

        elif query_data == "reject":
            logger.info("Пост отклонен модератором")
            pending['result']['approved'] = False
            pending['event'].set()

            # Обновляем сообщение
            try:
                await self.bot.edit_message_caption(
                    chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
                    message_id=message_id,
                    caption=f"{pending['post'].text}\n\n❌ **ОТКЛОНЕНО**",
                    parse_mode='Markdown'
                )
            except TelegramError:
                try:
                    await self.bot.edit_message_text(
                        chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
                        message_id=message_id,
                        text=f"{pending['post'].text}\n\n❌ **ОТКЛОНЕНО**",
                        parse_mode='Markdown'
                    )
                except TelegramError as e:
                    logger.error(f"Не удалось обновить сообщение: {e}")

        elif query_data == "edit":
            logger.info("Запрошено редактирование поста")
            # Отправляем инструкцию по редактированию
            await self.bot.send_message(
                chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
                text="📝 Отправьте отредактированный текст поста в ответ на это сообщение.\n\n"
                     "Или нажмите /cancel для отмены редактирования.",
                reply_to_message_id=message_id
            )
            # Редактирование будет обработано в handler текстовых сообщений

    async def handle_edit_message(self, text: str, reply_to_message_id: int, user_id: int):
        """
        Обработка отредактированного текста поста

        Args:
            text: Новый текст поста
            reply_to_message_id: ID сообщения, на которое отвечаем
            user_id: ID пользователя
        """
        # Проверяем, что это админ
        if user_id != bot.config.config.TELEGRAM_ADMIN_ID:
            return

        # Ищем пост в ожидающих (может быть reply на оригинальное сообщение)
        if reply_to_message_id not in self.pending_posts:
            logger.warning(f"Пост {reply_to_message_id} не найден для редактирования")
            return

        if text == "/cancel":
            await self.bot.send_message(
                chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
                text="❌ Редактирование отменено"
            )
            return

        pending = self.pending_posts[reply_to_message_id]

        logger.info("Пост отредактирован модератором")
        pending['result']['approved'] = True
        pending['result']['edited_text'] = text
        pending['event'].set()

        await self.bot.send_message(
            chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
            text="✅ Изменения приняты, пост будет опубликован с новым текстом"
        )


# Глобальный объект модератора
moderator: Optional[Moderator] = None


def init_moderator(bot: Bot) -> Moderator:
    """
    Инициализация глобального модератора

    Args:
        bot: Объект Telegram Bot

    Returns:
        Moderator
    """
    global moderator
    moderator = Moderator(bot)
    return moderator
