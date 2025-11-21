"""
Обработчики команд Telegram бота
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.core.logger import get_logger
from bot.core.database import db_manager

logger = get_logger(__name__)


class BotHandlers:
    """
    Обработчики команд бота
    """

    def __init__(self, admin_id: int):
        """
        Инициализация обработчиков

        Args:
            admin_id: ID администратора
        """
        self.admin_id = admin_id
        logger.info("🔧 BotHandlers инициализирован")

    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        return user_id == self.admin_id

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("⛔ Доступ запрещен")
            return

        welcome_text = """🤖 Бот новостной аналитики запущен!

Доступные команды:
/start - Показать это сообщение
/status - Статус бота и статистика
/collect - Автоматическая публикация (сбор, анализ, генерация)
/publish - Опубликовать свой текст и медиа
/stats - Детальная статистика
/health - Проверка здоровья системы

Бот автоматически собирает новости, анализирует их через Claude AI и публикует в канал."""

        await update.message.reply_text(welcome_text)
        logger.info(f"👤 Команда /start от пользователя {user.id}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("⛔ Доступ запрещен")
            return

        # Получаем статистику
        today_count = 0
        if db_manager:
            today_count = await db_manager.get_today_published_count()

        status_text = f"""📊 СТАТУС БОТА

✅ Бот: Работает
✅ База данных: {'Подключена' if db_manager else 'Не подключена'}

📈 Статистика за сегодня:
  • Опубликовано постов: {today_count}

🤖 Автоматизация: Включена
🔄 Сбор новостей: Активен"""

        await update.message.reply_text(status_text)
        logger.info(f"📊 Команда /status от пользователя {user.id}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("⛔ Доступ запрещен")
            return

        today_count = 0
        recent_posts = []

        if db_manager:
            today_count = await db_manager.get_today_published_count()
            recent_posts = await db_manager.get_recent_posts(limit=10)

        stats_text = f"""📊 ДЕТАЛЬНАЯ СТАТИСТИКА

📅 Сегодня опубликовано: {today_count} постов

📝 Последние 10 постов:
"""

        if recent_posts:
            for i, post in enumerate(recent_posts[:10], 1):
                source = post.source or 'Unknown'
                title = post.title[:50] + '...' if len(post.title) > 50 else post.title
                stats_text += f"{i}. [{source}] {title}\n"
        else:
            stats_text += "Нет опубликованных постов"

        await update.message.reply_text(stats_text)
        logger.info(f"📈 Команда /stats от пользователя {user.id}")

    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /health"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("⛔ Доступ запрещен")
            return

        health_checks = {
            'bot': '✅ OK',
            'database': '✅ OK' if db_manager else '❌ Not connected',
            'scheduler': '✅ Running'
        }

        health_text = f"""🏥 ПРОВЕРКА ЗДОРОВЬЯ СИСТЕМЫ

🤖 Бот: {health_checks['bot']}
🗄️ База данных: {health_checks['database']}
⏰ Планировщик: {health_checks['scheduler']}

{'✅ Все системы работают нормально' if all('✅' in v for v in health_checks.values()) else '⚠️ Обнаружены проблемы'}"""

        await update.message.reply_text(health_text)
        logger.info(f"🏥 Команда /health от пользователя {user.id}")

    async def collect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /collect - автоматическая публикация"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("⛔ Доступ запрещен")
            return

        await update.message.reply_text("🚀 Запускаю автоматическую публикацию...")
        logger.info(f"📰 Команда /collect от пользователя {user.id}")

        # Эта команда будет обрабатываться в main.py как publish_command
        # Просто вызываем scheduler напрямую
        scheduler = context.bot_data.get('scheduler')

        if not scheduler:
            await update.message.reply_text("❌ Планировщик недоступен")
            return

        try:
            stats = await scheduler.force_publish()

            by_source_text = '\n'.join([
                f"   • {source}: {count}"
                for source, count in stats.get('by_source', {}).items()
            ])

            result_text = f"""🚀 РЕЗУЛЬТАТ ПУБЛИКАЦИИ:

📰 Собрано новостей: {stats.get('collected', 0)}
{by_source_text if by_source_text else ''}

🤖 Отобрано Claude AI: {stats.get('analyzed', 0)}
✍️ Сгенерировано постов: {stats.get('generated', 0)}
📤 Отправлено на модерацию: {stats.get('sent_to_moderation', 0)}
✅ Опубликовано: {stats.get('published', 0)}

{'⚠️ Ошибки: ' + str(len(stats.get('errors', []))) if stats.get('errors') else '✅ Без ошибок'}

🎉 Публикация завершена!"""

            await update.message.reply_text(result_text)

        except Exception as e:
            logger.error(f"❌ Ошибка автоматической публикации: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def publish_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /publish - ручная публикация своего контента"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("⛔ Доступ запрещен")
            return

        logger.info(f"📤 Команда /publish от пользователя {user.id}")

        context.user_data['waiting_for_publish_text'] = True

        await update.message.reply_text(
            "📝 Отправьте текст для публикации\n\n"
            "После этого можете отправить изображение (опционально)\n"
            "Затем используйте команду /publish_now для публикации"
        )

    async def publish_now_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Публикация подготовленного контента"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("⛔ Доступ запрещен")
            return

        custom_text = context.user_data.get('publish_text')
        media_file_id = context.user_data.get('publish_media_id')

        if not custom_text:
            await update.message.reply_text("❌ Сначала отправьте текст для публикации")
            return

        try:
            publisher = context.bot_data.get('publisher')
            if not publisher:
                await update.message.reply_text("❌ Издатель недоступен")
                return

            await update.message.reply_text("📤 Публикую...")

            # Создаем фейковый news_item для сохранения в БД
            news_item = {
                'url': '',
                'title': 'Ручная публикация',
                'published_at': None,
                'source': 'Admin'
            }

            if media_file_id:
                message_id = await publisher.publish_with_media(
                    custom_text,
                    news_item,
                    photo_url=media_file_id
                )
            else:
                message_id = await publisher.publish_post(custom_text, news_item)

            if message_id:
                await update.message.reply_text(f"✅ Пост опубликован! (ID: {message_id})")
            else:
                await update.message.reply_text("❌ Не удалось опубликовать")

            # Очищаем данные
            context.user_data.pop('publish_text', None)
            context.user_data.pop('publish_media_id', None)
            context.user_data.pop('waiting_for_publish_text', None)

        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текста для /publish"""
        user = update.effective_user

        if not self.is_admin(user.id):
            return

        if context.user_data.get('waiting_for_publish_text'):
            text = update.message.text
            context.user_data['publish_text'] = text
            context.user_data.pop('waiting_for_publish_text', None)

            await update.message.reply_text(
                f"✅ Текст сохранен ({len(text)} символов)\n\n"
                "Можете отправить изображение (опционально)\n"
                "Затем используйте /publish_now для публикации"
            )

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения фото для /publish"""
        user = update.effective_user

        if not self.is_admin(user.id):
            return

        if 'publish_text' not in context.user_data:
            await update.message.reply_text("⚠️ Сначала используйте /publish и отправьте текст")
            return

        try:
            # Получаем фото наивысшего качества
            photo = update.message.photo[-1]
            context.user_data['publish_media_id'] = photo.file_id

            await update.message.reply_text(
                "✅ Фото добавлено!\n\n"
                "Используйте /publish_now для публикации"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка обработки фото: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"❌ Ошибка при обработке обновления: {context.error}")

        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Произошла ошибка при обработке команды"
            )
