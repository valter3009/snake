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


async def collect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /collect - принудительный сбор и публикация новостей"""
    global scheduler

    user = update.effective_user
    handlers = context.bot_data.get('handlers')

    if not handlers or not handlers.is_admin(user.id):
        await update.message.reply_text("⛔ Доступ запрещен")
        return

    await update.message.reply_text("🚀 Запускаю принудительный сбор новостей...")

    try:
        # Запускаем принудительную публикацию
        stats = await scheduler.force_publish()

        # Формируем детальный отчет
        by_source_text = '\n'.join([
            f"   • {source}: {count}"
            for source, count in stats.get('by_source', {}).items()
        ])

        result_text = f"""🚀 РЕЗУЛЬТАТ СБОРА:

📰 Собрано новостей: {stats.get('collected', 0)}
{by_source_text if by_source_text else ''}

🤖 Отобрано Claude AI: {stats.get('analyzed', 0)}
   • Анализ: ✅ завершен

✍️ Сгенерировано постов: {stats.get('generated', 0)}

📤 Отправлено на модерацию: {stats.get('sent_to_moderation', 0)}
✅ Опубликовано: {stats.get('published', 0)}

{'⚠️ Ошибки: ' + str(len(stats.get('errors', []))) if stats.get('errors') else '✅ Без ошибок'}

🎉 Сбор завершен!"""

        await update.message.reply_text(result_text)

    except Exception as e:
        logger.error(f"❌ Ошибка принудительного сбора: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def publish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /publish - прямая публикация контента от админа в канал"""
    user = update.effective_user
    handlers = context.bot_data.get('handlers')
    publisher = context.bot_data.get('publisher')

    if not handlers or not handlers.is_admin(user.id):
        await update.message.reply_text("⛔ Доступ запрещен")
        return

    if not publisher:
        await update.message.reply_text("❌ Публикатор не инициализирован")
        return

    # Проверяем, есть ли контент для публикации
    message = update.message

    # Если это reply на предыдущее сообщение
    if message.reply_to_message:
        content_message = message.reply_to_message
    else:
        # Если нет, то ожидаем следующее сообщение
        await update.message.reply_text("""📝 Отправьте контент для публикации:

• Текст
• Фото с подписью
• Видео с подписью

Контент будет опубликован в канал БЕЗ изменений.""")
        return

    try:
        # Публикуем контент напрямую
        if content_message.photo:
            # Публикуем фото с подписью
            photo = content_message.photo[-1]  # Берем самое большое фото
            caption = content_message.caption or ""

            sent_message = await context.bot.send_photo(
                chat_id=publisher.channel_id,
                photo=photo.file_id,
                caption=caption,
                parse_mode=None
            )

            logger.info(f"✅ Фото опубликовано админом (msg_id: {sent_message.message_id})")
            await update.message.reply_text(f"✅ Фото опубликовано в канал!\nID сообщения: {sent_message.message_id}")

        elif content_message.video:
            # Публикуем видео с подписью
            video = content_message.video
            caption = content_message.caption or ""

            sent_message = await context.bot.send_video(
                chat_id=publisher.channel_id,
                video=video.file_id,
                caption=caption,
                parse_mode=None
            )

            logger.info(f"✅ Видео опубликовано админом (msg_id: {sent_message.message_id})")
            await update.message.reply_text(f"✅ Видео опубликовано в канал!\nID сообщения: {sent_message.message_id}")

        elif content_message.text:
            # Публикуем текст
            text = content_message.text

            sent_message = await context.bot.send_message(
                chat_id=publisher.channel_id,
                text=text,
                parse_mode=None
            )

            logger.info(f"✅ Текст опубликован админом (msg_id: {sent_message.message_id})")
            await update.message.reply_text(f"✅ Текст опубликован в канал!\nID сообщения: {sent_message.message_id}")

        else:
            await update.message.reply_text("❌ Неподдерживаемый тип контента. Отправьте текст, фото или видео.")

    except Exception as e:
        logger.error(f"❌ Ошибка публикации контента админа: {e}")
        await update.message.reply_text(f"❌ Ошибка публикации: {e}")


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


async def main():
    """Главная функция"""
    global scheduler

    logger.info("=" * 60)
    logger.info("🤖 ЗАПУСК TELEGRAM БОТА НОВОСТНОЙ АНАЛИТИКИ")
    logger.info("=" * 60)

    # Инициализируем переменную для graceful shutdown
    telegram_app = None

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
        telegram_app.add_handler(CommandHandler("collect", collect_command))
        telegram_app.add_handler(CommandHandler("publish", publish_command))

        # Callback handlers
        telegram_app.add_handler(CallbackQueryHandler(moderation_callback))

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

        # Инициализация application
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        # Запускаем scheduler в фоне
        asyncio.create_task(scheduler.start())

        logger.info("=" * 60)
        logger.info("✅ БОТ УСПЕШНО ЗАПУЩЕН И РАБОТАЕТ!")
        logger.info("=" * 60)

        # Создаем событие для остановки
        stop_signal = asyncio.Event()

        # Ожидаем бесконечно (пока не будет прерывания)
        await stop_signal.wait()

    except KeyboardInterrupt:
        logger.info("⚠️ Получен сигнал прерывания (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise
    finally:
        logger.info("👋 Завершение работы бота")

        # Graceful shutdown
        try:
            if telegram_app is not None:
                logger.info("🛑 Остановка Telegram бота...")
                await telegram_app.updater.stop()
                await telegram_app.stop()
                await telegram_app.shutdown()
                logger.info("✅ Telegram бот остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке бота: {e}")

        # Останавливаем scheduler
        try:
            if scheduler is not None:
                logger.info("🛑 Остановка планировщика...")
                await scheduler.stop()
                logger.info("✅ Планировщик остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке планировщика: {e}")

        # Закрываем БД
        if db_manager:
            try:
                logger.info("🛑 Закрытие базы данных...")
                await db_manager.close()
                logger.info("✅ База данных закрыта")
            except Exception as e:
                logger.error(f"❌ Ошибка при закрытии БД: {e}")


if __name__ == "__main__":
    # Запускаем основную функцию
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Прерывание работы")
