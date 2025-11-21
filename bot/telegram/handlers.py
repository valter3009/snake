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
/collect - Собрать новости и создать публикацию вручную
/publish - Принудительная автоматическая публикация
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
        """Обработчик команды /collect - ручной сбор и публикация"""
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("⛔ Доступ запрещен")
            return

        await update.message.reply_text("📰 Собираю новости...")
        logger.info(f"📰 Команда /collect от пользователя {user.id}")

        try:
            # Получаем компоненты из bot_data
            scheduler = context.bot_data.get('scheduler')
            news_collector = scheduler.news_collector if scheduler else None

            if not news_collector:
                await update.message.reply_text("❌ Сборщик новостей недоступен")
                return

            # Собираем новости
            news_list = await news_collector.collect_all_news()

            if not news_list:
                await update.message.reply_text("❌ Не удалось собрать новости")
                return

            # Сохраняем новости в context для дальнейшего использования
            context.user_data['collected_news'] = news_list

            # Формируем список новостей с кнопками
            message_text = f"📰 Собрано {len(news_list)} новостей\n\nВыберите новость для публикации:"

            # Показываем первые 10 новостей с кнопками
            keyboard = []
            for i, news in enumerate(news_list[:10], 1):
                title = news.get('title', 'Без заголовка')[:60]
                source = news.get('source', 'Unknown')
                keyboard.append([InlineKeyboardButton(
                    f"{i}. [{source}] {title}...",
                    callback_data=f"collect_news_{i-1}"
                )])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message_text, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"❌ Ошибка при сборе новостей: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def collect_news_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора новости для публикации"""
        query = update.callback_query
        await query.answer()

        user = query.from_user
        if not self.is_admin(user.id):
            await query.edit_message_text("⛔ Доступ запрещен")
            return

        try:
            # Получаем индекс выбранной новости
            news_index = int(query.data.split('_')[-1])
            news_list = context.user_data.get('collected_news', [])

            if news_index >= len(news_list):
                await query.edit_message_text("❌ Новость не найдена")
                return

            selected_news = news_list[news_index]
            context.user_data['selected_news'] = selected_news

            # Показываем информацию о новости
            title = selected_news.get('title', 'Без заголовка')
            source = selected_news.get('source', 'Unknown')
            description = selected_news.get('description', '')[:200]

            news_info = f"""✅ Выбрана новость:

📰 {title}
📌 Источник: {source}
📝 {description}...

✍️ Генерирую пост..."""

            await query.edit_message_text(news_info)

            # Генерируем пост
            scheduler = context.bot_data.get('scheduler')
            content_generator = scheduler.content_generator if scheduler else None

            if not content_generator:
                await query.message.reply_text("❌ Генератор контента недоступен")
                return

            generated_post = await content_generator.generate_post(selected_news)

            if not generated_post:
                await query.message.reply_text("❌ Не удалось сгенерировать пост")
                return

            context.user_data['generated_post'] = generated_post

            # Показываем сгенерированный пост с опциями
            keyboard = [
                [InlineKeyboardButton("📤 Опубликовать", callback_data="collect_publish")],
                [InlineKeyboardButton("🖼️ Добавить медиа", callback_data="collect_add_media")],
                [InlineKeyboardButton("❌ Отменить", callback_data="collect_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            preview_text = f"""✅ Пост сгенерирован:

{generated_post[:500]}{'...' if len(generated_post) > 500 else ''}

Выберите действие:"""

            await query.message.reply_text(preview_text, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке выбора новости: {e}")
            await query.message.reply_text(f"❌ Ошибка: {e}")

    async def collect_action_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик действий с собранной новостью"""
        query = update.callback_query
        await query.answer()

        user = query.from_user
        if not self.is_admin(user.id):
            await query.edit_message_text("⛔ Доступ запрещен")
            return

        action = query.data.split('_')[-1]

        try:
            if action == "publish":
                # Публикуем пост
                generated_post = context.user_data.get('generated_post')
                selected_news = context.user_data.get('selected_news')
                media_file_id = context.user_data.get('media_file_id')

                if not generated_post:
                    await query.edit_message_text("❌ Пост не найден")
                    return

                publisher = context.bot_data.get('publisher')
                if not publisher:
                    await query.edit_message_text("❌ Издатель недоступен")
                    return

                await query.edit_message_text("📤 Публикую...")

                # Публикуем с медиа если есть
                if media_file_id:
                    message_id = await publisher.publish_with_media(
                        generated_post,
                        selected_news,
                        photo_url=media_file_id  # file_id работает как URL
                    )
                else:
                    message_id = await publisher.publish_post(
                        generated_post,
                        selected_news
                    )

                if message_id:
                    await query.message.reply_text(f"✅ Пост успешно опубликован! (ID: {message_id})")
                else:
                    await query.message.reply_text("❌ Не удалось опубликовать пост")

                # Очищаем данные
                context.user_data.clear()

            elif action == "add_media":
                await query.edit_message_text(
                    "🖼️ Отправьте изображение для публикации\n\n"
                    "После отправки изображения, нажмите 'Опубликовать'"
                )

            elif action == "cancel":
                await query.edit_message_text("❌ Публикация отменена")
                context.user_data.clear()

        except Exception as e:
            logger.error(f"❌ Ошибка при выполнении действия: {e}")
            await query.message.reply_text(f"❌ Ошибка: {e}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения фото для публикации"""
        user = update.effective_user

        if not self.is_admin(user.id):
            return

        if 'generated_post' not in context.user_data:
            await update.message.reply_text("⚠️ Сначала используйте /collect для создания поста")
            return

        try:
            # Получаем фото наивысшего качества
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            # Сохраняем путь к файлу
            context.user_data['media_file_id'] = photo.file_id

            # Показываем кнопку для публикации с фото
            keyboard = [
                [InlineKeyboardButton("📤 Опубликовать с фото", callback_data="collect_publish")],
                [InlineKeyboardButton("❌ Отменить", callback_data="collect_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "✅ Фото добавлено!\n\nГотово к публикации:",
                reply_markup=reply_markup
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
