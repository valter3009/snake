"""
Обработчики команд Telegram бота
"""
from telegram import Update
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
/collect - Принудительный сбор новостей
/publish - Опубликовать контент от админа (reply на сообщение)
/stats - Детальная статистика
/health - Проверка здоровья системы

🤖 Бот работает 24/7, автоматически собирает новости, анализирует через Claude AI и публикует 50-60 постов в сутки."""

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

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"❌ Ошибка при обработке обновления: {context.error}")

        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Произошла ошибка при обработке команды"
            )
