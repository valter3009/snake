"""
Главная точка входа Telegram бота новостной аналитики
"""
import asyncio
import signal
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from bot.config import init_config
from bot.core.logger import setup_logger
from bot.core.database import init_database, db_manager
from bot.news.collector import NewsCollector
from bot.news.analyzer import NewsAnalyzer
from bot.news.extractor import NewsExtractor
from bot.content.generator import ContentGenerator
from bot.telegram.publisher import ChannelPublisher
from bot.telegram.moderator import PostModerator
from bot.telegram.handlers import BotHandlers
from bot.media.handler import MediaHandler
from bot.scheduler.tasks import PublishingScheduler

# Глобальный логгер
logger = setup_logger("bot.main", "INFO")

# Глобальные компоненты
scheduler = None


async def publish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /publish - принудительная публикация"""
    global scheduler

    user = update.effective_user
    handlers = context.bot_data.get('handlers')

    if not handlers or not handlers.is_admin(user.id):
        await update.message.reply_text("⛔ Доступ запрещен")
        return

    await update.message.reply_text("🚀 Запускаю принудительную публикацию...")

    try:
        # Запускаем принудительную публикацию
        stats = await scheduler.force_publish()

        # Формируем детальный отчет
        by_source_text = '\n'.join([
            f"   • {source}: {count}"
            for source, count in stats.get('by_source', {}).items()
        ])

        result_text = f"""🚀 РЕЗУЛЬТАТ ПУБЛИКАЦИИ:

📰 Собрано новостей: {stats.get('collected', 0)}
{by_source_text if by_source_text else ''}

🤖 Отобрано Claude AI: {stats.get('analyzed', 0)}
   • Анализ: ✅ завершен

✍️ Сгенерировано постов: {stats.get('generated', 0)}

📤 Отправлено на модерацию: {stats.get('sent_to_moderation', 0)}
✅ Опубликовано: {stats.get('published', 0)}

{'⚠️ Ошибки: ' + str(len(stats.get('errors', []))) if stats.get('errors') else '✅ Без ошибок'}

🎉 Публикация завершена!"""

        await update.message.reply_text(result_text)

    except Exception as e:
        logger.error(f"❌ Ошибка принудительной публикации: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback'ов от модерации"""
    query = update.callback_query
    moderator = context.bot_data.get('moderator')
    publisher = context.bot_data.get('publisher')

    if not moderator or not publisher:
        await query.answer("⚠️ Система модерации недоступна")
        return

    try:
        action, post_data = await moderator.handle_moderation_callback(query, context.bot)

        if action == 'approve' and post_data:
            # Публикуем одобренный пост
            try:
                content = post_data.get('content', '')
                news_item = post_data.get('news_item', {})

                message_id = await publisher.publish_post(content, news_item)

                if message_id:
                    logger.info(f"✅ Пост опубликован после модерации (msg_id: {message_id})")
                    await context.bot.send_message(
                        chat_id=query.from_user.id,
                        text=f"✅ Пост успешно опубликован! (ID: {message_id})"
                    )
            except Exception as e:
                logger.error(f"❌ Ошибка публикации одобренного поста: {e}")
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text=f"❌ Ошибка публикации: {e}"
                )

    except Exception as e:
        logger.error(f"❌ Ошибка обработки callback модерации: {e}")


async def post_init(application: Application):
    """Инициализация после запуска бота"""
    global scheduler

    logger.info("🔧 Запуск post_init...")

    # Запускаем планировщик в фоне
    if scheduler:
        asyncio.create_task(scheduler.start())
        logger.info("✅ Планировщик запущен в фоне")


async def post_shutdown(application: Application):
    """Graceful shutdown"""
    global scheduler

    logger.info("🛑 Начинаю graceful shutdown...")

    # Останавливаем планировщик
    if scheduler:
        await scheduler.stop()
        logger.info("✅ Планировщик остановлен")

    # Закрываем БД
    if db_manager:
        await db_manager.close()
        logger.info("✅ База данных закрыта")

    logger.info("✅ Shutdown завершен")


async def main():
    """Главная функция"""
    global scheduler

    logger.info("=" * 60)
    logger.info("🤖 ЗАПУСК TELEGRAM БОТА НОВОСТНОЙ АНАЛИТИКИ")
    logger.info("=" * 60)

    try:
        # 1. Загружаем конфигурацию
        logger.info("📋 Загрузка конфигурации...")
        config = init_config()

        # 2. Инициализируем базу данных
        logger.info("🗄️ Инициализация базы данных...")
        try:
            await init_database(config.DATABASE_URL)
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            logger.warning("⚠️ Продолжаю без БД (функциональность ограничена)")

        # 3. Инициализируем компоненты
        logger.info("🔧 Инициализация компонентов...")

        # News components
        news_collector = NewsCollector(
            newsapi_key=config.NEWS_API_KEY,
            max_age_hours=config.NEWS_MAX_AGE_HOURS
        )
        news_analyzer = NewsAnalyzer(api_key=config.ANTHROPIC_API_KEY)
        news_extractor = NewsExtractor()

        # Content components
        content_generator = ContentGenerator(api_key=config.ANTHROPIC_API_KEY)

        # Telegram components
        telegram_app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        publisher = ChannelPublisher(
            bot=telegram_app.bot,
            channel_id=config.TELEGRAM_CHANNEL_ID
        )
        moderator = PostModerator(
            admin_id=config.TELEGRAM_ADMIN_ID,
            timeout=config.MODERATION_TIMEOUT
        )
        handlers = BotHandlers(admin_id=config.TELEGRAM_ADMIN_ID)

        # Media component
        media_handler = MediaHandler()

        # Scheduler
        scheduler = PublishingScheduler(
            news_collector=news_collector,
            news_analyzer=news_analyzer,
            news_extractor=news_extractor,
            content_generator=content_generator,
            publisher=publisher,
            moderator=moderator,
            media_handler=media_handler,
            config=config
        )

        logger.info("✅ Все компоненты инициализированы")

        # 4. Регистрируем обработчики команд
        logger.info("📝 Регистрация обработчиков...")

        telegram_app.add_handler(CommandHandler("start", handlers.start_command))
        telegram_app.add_handler(CommandHandler("status", handlers.status_command))
        telegram_app.add_handler(CommandHandler("stats", handlers.stats_command))
        telegram_app.add_handler(CommandHandler("health", handlers.health_command))
        telegram_app.add_handler(CommandHandler("collect", handlers.collect_command))
        telegram_app.add_handler(CommandHandler("publish", publish_command))

        # Callback handlers для /collect
        telegram_app.add_handler(CallbackQueryHandler(
            handlers.collect_news_callback,
            pattern=r'^collect_news_\d+$'
        ))
        telegram_app.add_handler(CallbackQueryHandler(
            handlers.collect_action_callback,
            pattern=r'^collect_(publish|add_media|cancel)$'
        ))

        # Callback handler для модерации
        telegram_app.add_handler(CallbackQueryHandler(
            moderation_callback,
            pattern=r'^(approve|reject|edit)_'
        ))

        # Message handler для фото (только для админа)
        telegram_app.add_handler(MessageHandler(
            filters.PHOTO & filters.User(user_id=config.TELEGRAM_ADMIN_ID),
            handlers.handle_photo
        ))

        # Error handler
        telegram_app.add_error_handler(handlers.error_handler)

        # Сохраняем компоненты в bot_data для доступа из handlers
        telegram_app.bot_data['handlers'] = handlers
        telegram_app.bot_data['moderator'] = moderator
        telegram_app.bot_data['publisher'] = publisher
        telegram_app.bot_data['scheduler'] = scheduler

        logger.info("✅ Обработчики зарегистрированы")

        # 5. Запускаем бота
        logger.info("🚀 Запуск бота...")

        # Инициализируем приложение
        await telegram_app.initialize()
        await telegram_app.start()

        # Вызываем post_init
        await post_init(telegram_app)

        # Запускаем polling
        logger.info("=" * 60)
        logger.info("✅ БОТ УСПЕШНО ЗАПУЩЕН И РАБОТАЕТ!")
        logger.info("=" * 60)

        await telegram_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        # Ждем сигнала завершения
        stop_signals = (signal.SIGINT, signal.SIGTERM)
        loop = asyncio.get_running_loop()

        # Создаем future для ожидания завершения
        stop_event = asyncio.Event()

        def signal_handler(signum, frame):
            logger.info(f"⚠️ Получен сигнал {signum}")
            stop_event.set()

        for sig in stop_signals:
            signal.signal(sig, signal_handler)

        # Ждем сигнала завершения
        await stop_event.wait()

    except KeyboardInterrupt:
        logger.info("⚠️ Получен сигнал прерывания (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise
    finally:
        logger.info("👋 Завершение работы бота")

        # Graceful shutdown
        try:
            await post_shutdown(telegram_app)
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
        except Exception as e:
            logger.error(f"❌ Ошибка при shutdown: {e}")


if __name__ == "__main__":
    # Запускаем основную функцию
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Прерывание работы")
