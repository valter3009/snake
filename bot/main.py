"""
Главный модуль бота
"""
import logging
import asyncio
import signal
from typing import Optional

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

import bot.config
from bot.database import init_database, db_manager
from bot.news_collector import init_news_collector, news_collector
from bot.news_analyzer import init_news_analyzer
from bot.post_generator import init_post_generator
from bot.media_handler import init_media_handler, media_handler
from bot.moderator import init_moderator, moderator
from bot.scheduler import init_scheduler, scheduler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class NewsBot:
    """Главный класс бота"""

    def __init__(self):
        self.application: Optional[Application] = None
        self.shutdown_event = asyncio.Event()

    async def initialize(self):
        """Инициализация всех компонентов"""
        logger.info("Инициализация бота...")

        # Загружаем конфигурацию
        bot.config.init_config()
        logger.info("Конфигурация загружена")

        # Инициализируем БД
        init_database()
        await db_manager.init_db()
        logger.info("База данных инициализирована")

        # Инициализируем компоненты
        init_news_collector()
        init_news_analyzer()
        init_post_generator()
        init_media_handler()

        # Создаем Telegram приложение
        self.application = Application.builder().token(bot.config.config.TELEGRAM_BOT_TOKEN).build()

        # Инициализируем модератор и планировщик
        init_moderator(self.application.bot)
        init_scheduler(self.application.bot)

        # Регистрируем handlers
        self._register_handlers()

        logger.info("Бот инициализирован")

    def _register_handlers(self):
        """Регистрация обработчиков команд и callback'ов"""
        # Команды
        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(CommandHandler("publish", self._cmd_publish))

        # Callback от inline кнопок модерации
        self.application.add_handler(CallbackQueryHandler(self._handle_moderation_callback))

        # Текстовые сообщения (для редактирования постов)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.REPLY, self._handle_edit_reply)
        )

        logger.info("Handlers зарегистрированы")

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        if update.effective_user.id == bot.config.config.TELEGRAM_ADMIN_ID:
            await update.message.reply_text(
                "👋 Привет, админ!\n\n"
                "Доступные команды:\n"
                "/status - статус бота\n"
                "/publish - принудительная публикация"
            )
        else:
            await update.message.reply_text("👋 Привет!")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        if update.effective_user.id != bot.config.config.TELEGRAM_ADMIN_ID:
            return

        today_count = await db_manager.get_today_published_count()
        is_running = scheduler.is_running

        status_text = f"""📊 **Статус бота**

Планировщик: {'🟢 Работает' if is_running else '🔴 Остановлен'}
Постов сегодня: {today_count}
Лимит постов: {bot.config.config.MIN_POSTS_PER_DAY}-{bot.config.config.MAX_POSTS_PER_DAY} в день

Время публикации: {bot.config.config.PUBLISH_START_HOUR}:00 - {bot.config.config.PUBLISH_END_HOUR}:00 МСК
Интервал сбора: {bot.config.config.MIN_COLLECTION_INTERVAL}-{bot.config.config.MAX_COLLECTION_INTERVAL} мин
"""
        await update.message.reply_text(status_text, parse_mode='Markdown')

    async def _cmd_publish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /publish (принудительная публикация)"""
        if update.effective_user.id != bot.config.config.TELEGRAM_ADMIN_ID:
            return

        await update.message.reply_text("🚀 Запускаю принудительную публикацию...")

        try:
            await scheduler.publish_now()
            await update.message.reply_text("✅ Публикация завершена!")
        except Exception as e:
            logger.error(f"Ошибка принудительной публикации: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def _handle_moderation_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback от inline кнопок модерации"""
        query = update.callback_query
        await query.answer()

        await moderator.handle_moderation_callback(
            query_data=query.data,
            message_id=query.message.message_id,
            user_id=query.from_user.id
        )

    async def _handle_edit_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ответов на сообщения (для редактирования постов)"""
        if update.message.reply_to_message:
            await moderator.handle_edit_message(
                text=update.message.text,
                reply_to_message_id=update.message.reply_to_message.message_id,
                user_id=update.effective_user.id
            )

    async def start(self):
        """Запуск бота"""
        logger.info("Запуск бота...")

        # Инициализация
        await self.initialize()

        # Запускаем планировщик
        await scheduler.start()

        # Запускаем Telegram bot polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)

        logger.info("Бот запущен и работает")

        # Уведомляем админа
        try:
            await self.application.bot.send_message(
                chat_id=bot.config.config.TELEGRAM_ADMIN_ID,
                text="🤖 Бот запущен и готов к работе!"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление админу: {e}")

        # Ждём сигнала завершения
        await self.shutdown_event.wait()

    async def stop(self):
        """Остановка бота"""
        logger.info("Остановка бота...")

        # Останавливаем планировщик
        if scheduler:
            await scheduler.stop()

        # Останавливаем polling
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                logger.error(f"Ошибка при остановке Telegram приложения: {e}")

        # Закрываем соединения
        if news_collector:
            await news_collector.close()
        if media_handler:
            await media_handler.close()
        if db_manager:
            await db_manager.close()

        logger.info("Бот остановлен")

        # Сигнализируем о завершении
        self.shutdown_event.set()

    def handle_signal(self, signum, frame):
        """Обработчик системных сигналов"""
        logger.info(f"Получен сигнал {signum}, завершаем работу...")
        asyncio.create_task(self.stop())


async def main():
    """Главная функция"""
    bot = NewsBot()

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(bot.stop()))
    signal.signal(signal.SIGTERM, lambda s, f: asyncio.create_task(bot.stop()))

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Получен Ctrl+C")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем")
