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
import bot.database
import bot.news_collector
import bot.news_analyzer
import bot.post_generator
import bot.media_handler
import bot.moderator
import bot.scheduler
import bot.article_extractor

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
        bot.database.init_database()
        await bot.database.db_manager.init_db()
        logger.info("База данных инициализирована")

        # Инициализируем компоненты
        bot.article_extractor.init_article_extractor()
        bot.news_collector.init_news_collector()
        bot.news_analyzer.init_news_analyzer()
        bot.post_generator.init_post_generator()
        bot.media_handler.init_media_handler()

        # Создаем Telegram приложение
        self.application = Application.builder().token(bot.config.config.TELEGRAM_BOT_TOKEN).build()

        # Инициализируем модератор и планировщик
        bot.moderator.init_moderator(self.application.bot)
        bot.scheduler.init_scheduler(self.application.bot)

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
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_message)
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

        today_count = await bot.database.db_manager.get_today_published_count()
        is_running = bot.scheduler.scheduler.is_running

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
            stats = await bot.scheduler.scheduler.publish_now()

            # Формируем детальный отчет
            report = "📊 **Результат публикации:**\n\n"
            report += f"📰 Собрано новостей: {stats.get('collected', 0)}\n"
            report += f"🤖 Отобрано Claude AI: {stats.get('analyzed', 0)}\n"
            report += f"✍️ Сгенерировано постов: {stats.get('generated', 0)}\n"
            report += f"📤 Отправлено на модерацию: {stats.get('sent_to_moderation', 0)}\n"
            report += f"✅ Опубликовано: {stats.get('published', 0)}\n"

            if 'error' in stats:
                report += f"\n⚠️ **Ошибка:** {stats['error']}"
                await update.message.reply_text(report, parse_mode='Markdown')
            elif stats.get('published', 0) > 0:
                report += "\n🎉 Публикация успешно завершена!"
                await update.message.reply_text(report, parse_mode='Markdown')
            else:
                report += "\n⚠️ Ни один пост не был опубликован. Проверьте логи для деталей."
                await update.message.reply_text(report, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Ошибка принудительной публикации: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Критическая ошибка: {str(e)}")

    async def _handle_moderation_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback от inline кнопок модерации"""
        query = update.callback_query
        await query.answer()

        await bot.moderator.moderator.handle_moderation_callback(
            query_data=query.data,
            message_id=query.message.message_id,
            user_id=query.from_user.id
        )

    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений (для редактирования постов)"""
        await bot.moderator.moderator.handle_edit_message(
            text=update.message.text,
            user_id=update.effective_user.id
        )

    async def start(self):
        """Запуск бота"""
        logger.info("Запуск бота...")

        # Инициализация
        await self.initialize()

        # Запускаем планировщик
        await bot.scheduler.scheduler.start()

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
        if bot.scheduler.scheduler:
            await bot.scheduler.scheduler.stop()

        # Останавливаем polling
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                logger.error(f"Ошибка при остановке Telegram приложения: {e}")

        # Закрываем соединения
        if bot.article_extractor.article_extractor:
            await bot.article_extractor.article_extractor.close()
        if bot.news_collector.news_collector:
            await bot.news_collector.news_collector.close()
        if bot.media_handler.media_handler:
            await bot.media_handler.media_handler.close()
        if bot.database.db_manager:
            await bot.database.db_manager.close()

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
