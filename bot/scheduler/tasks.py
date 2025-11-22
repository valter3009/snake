"""
Планировщик задач для автоматической публикации
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from bot.core.logger import get_logger
from bot.core.database import db_manager
from bot.news.collector import NewsCollector
from bot.news.analyzer import NewsAnalyzer
from bot.news.extractor import NewsExtractor
from bot.content.generator import ContentGenerator
from bot.telegram.publisher import ChannelPublisher
from bot.telegram.moderator import PostModerator
from bot.media.handler import MediaHandler

logger = get_logger(__name__)


class PublishingScheduler:
    """
    Планировщик автоматических публикаций
    """

    def __init__(
        self,
        news_collector: NewsCollector,
        news_analyzer: NewsAnalyzer,
        news_extractor: NewsExtractor,
        content_generator: ContentGenerator,
        publisher: ChannelPublisher,
        moderator: PostModerator,
        media_handler: MediaHandler,
        config
    ):
        """
        Инициализация планировщика

        Args:
            news_collector: Сборщик новостей
            news_analyzer: Анализатор новостей
            news_extractor: Экстрактор текста
            content_generator: Генератор контента
            publisher: Публикатор в канал
            moderator: Модератор постов
            media_handler: Обработчик медиа
            config: Конфигурация
        """
        self.news_collector = news_collector
        self.news_analyzer = news_analyzer
        self.news_extractor = news_extractor
        self.content_generator = content_generator
        self.publisher = publisher
        self.moderator = moderator
        self.media_handler = media_handler
        self.config = config

        self.is_running = False
        logger.info("🔧 PublishingScheduler инициализирован")

    async def start(self):
        """Запустить планировщик"""
        self.is_running = True
        logger.info("🚀 Планировщик запущен (режим: 1 пост каждые 15-30 минут)")

        while self.is_running:
            try:
                # Проверяем, находимся ли в рабочих часах
                # Получаем текущее время в UTC и конвертируем в timezone проекта
                current_hour = datetime.now(timezone.utc).astimezone(self.config.TIMEZONE).hour

                if self.config.PUBLISH_START_HOUR <= current_hour < self.config.PUBLISH_END_HOUR:
                    # Проверяем лимит публикаций за день
                    if db_manager:
                        today_count = await db_manager.get_today_published_count()
                        if today_count >= self.config.MAX_POSTS_PER_DAY:
                            logger.info(f"😴 Дневной лимит достигнут ({today_count}/{self.config.MAX_POSTS_PER_DAY})")
                            # Ждем до конца дня
                            interval = 3600  # 1 час
                            await asyncio.sleep(interval)
                            continue

                    # Собираем и публикуем ОДИН пост
                    stats = await self._collect_and_publish_news(single_post=True)

                    # Логируем результаты
                    logger.info(f"📊 Цикл завершен: сгенерировано {stats.get('generated', 0)}, отправлено на модерацию {stats.get('sent_to_moderation', 0)}")

                    # Рандомный интервал 15-30 минут (для ~40-50 постов в сутки)
                    interval = random.randint(15 * 60, 30 * 60)
                    logger.info(f"⏰ Следующий пост через {interval // 60} минут")

                else:
                    logger.info(f"😴 Вне рабочих часов (текущий час: {current_hour})")
                    # Ждем до начала рабочего времени
                    interval = 3600  # 1 час

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"❌ Ошибка в планировщике: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут при ошибке

    async def stop(self):
        """Остановить планировщик"""
        self.is_running = False
        logger.info("🛑 Планировщик остановлен")

    async def _collect_and_publish_news(self, single_post: bool = False) -> Dict[str, Any]:
        """
        Собрать новости и опубликовать

        Args:
            single_post: Если True, создать только 1 пост

        Returns:
            Статистика выполнения
        """
        stats = {
            'collected': 0,
            'by_source': {},
            'analyzed': 0,
            'generated': 0,
            'sent_to_moderation': 0,
            'published': 0,
            'errors': []
        }

        try:
            # ЭТАП 1: Сбор новостей
            logger.info("📰 Этап 1: Сбор новостей...")
            all_news = await self.news_collector.collect_all_news()
            stats['collected'] = len(all_news)

            # Подсчет по источникам
            for news in all_news:
                source = news.get('source', 'Unknown')
                stats['by_source'][source] = stats['by_source'].get(source, 0) + 1

            logger.info(f"  ✅ Собрано новостей: {stats['collected']}")
            for source, count in stats['by_source'].items():
                logger.info(f"    • {source}: {count}")

            if not all_news:
                logger.warning("⚠️ Новостей не найдено")
                return stats

            # Фильтруем уже опубликованные (если БД доступна)
            filtered_news = []
            if db_manager:
                for news in all_news:
                    url = news.get('url', '')
                    if url and not await db_manager.is_post_published(url):
                        filtered_news.append(news)
                logger.info(f"  ✅ После фильтрации дубликатов: {len(filtered_news)}")
            else:
                filtered_news = all_news

            if not filtered_news:
                logger.warning("⚠️ Все новости уже были опубликованы")
                return stats

            # ЭТАП 2: Анализ через Claude
            logger.info("🤖 Этап 2: Анализ через Claude AI...")
            # Если нужен только 1 пост, отбираем только 1 новость
            top_count = 1 if single_post else self.config.TOP_NEWS_COUNT
            top_news = await self.news_analyzer.select_top_news(
                filtered_news,
                top_count=top_count
            )
            stats['analyzed'] = len(top_news)
            logger.info(f"  ✅ Отобрано топовых новостей: {stats['analyzed']}")

            if not top_news:
                logger.warning("⚠️ Не удалось отобрать топовые новости")
                return stats

            # ЭТАП 3: Генерация постов
            logger.info("✍️ Этап 3: Генерация постов...")
            generated_posts = []

            for news_item in top_news:
                try:
                    # Извлекаем полный текст
                    url = news_item.get('url', '')
                    description = news_item.get('description', '')

                    full_text = await self.news_extractor.extract_with_fallback(url, description)

                    # Извлекаем изображение
                    image_url = await self.news_extractor.extract_image_url(url)
                    if image_url:
                        news_item['image_url'] = image_url
                        logger.info(f"  🖼️ Найдено изображение для {news_item.get('title', '')[:30]}...")

                    # Генерируем пост
                    post = await self.content_generator.generate_post(news_item, full_text)

                    if post:
                        generated_posts.append((news_item, post))
                        stats['generated'] += 1
                        logger.info(f"  ✅ Пост сгенерирован: {news_item.get('title', '')[:50]}...")

                except Exception as e:
                    logger.error(f"  ❌ Ошибка генерации поста: {e}")
                    stats['errors'].append(str(e))

            logger.info(f"  ✅ Всего сгенерировано постов: {stats['generated']}")

            if not generated_posts:
                logger.warning("⚠️ Не удалось сгенерировать посты")
                return stats

            # ЭТАП 4: Отправка на модерацию
            logger.info("📤 Этап 4: Отправка на модерацию...")

            for news_item, post in generated_posts:
                try:
                    # Отправляем на модерацию
                    post_id = await self.moderator.send_for_moderation(
                        bot=self.publisher.bot,
                        post_content=post,
                        news_item=news_item
                    )

                    stats['sent_to_moderation'] += 1
                    logger.info(f"  ✅ Отправлено на модерацию: {post_id}")

                except Exception as e:
                    logger.error(f"  ❌ Ошибка отправки на модерацию: {e}")
                    stats['errors'].append(str(e))

            logger.info(f"  ✅ Отправлено на модерацию: {stats['sent_to_moderation']}")

            # Проверяем лимит публикаций за день
            if db_manager:
                today_count = await db_manager.get_today_published_count()
                logger.info(f"📊 Опубликовано сегодня: {today_count}/{self.config.MAX_POSTS_PER_DAY}")

                if today_count >= self.config.MAX_POSTS_PER_DAY:
                    logger.info("⚠️ Достигнут дневной лимит публикаций")
                    return stats

            logger.info("✅ Цикл сбора и публикации завершен")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в цикле публикации: {e}")
            stats['errors'].append(str(e))

        return stats

    async def force_publish(self) -> Dict[str, Any]:
        """
        Принудительная публикация (для команды /collect)
        Публикует только ОДИН пост

        Returns:
            Детальная статистика
        """
        logger.info("🚀 Запуск принудительной публикации (1 пост)...")
        return await self._collect_and_publish_news(single_post=True)

    async def cleanup_old_data(self):
        """Очистка старых данных из БД"""
        if db_manager:
            try:
                logger.info("🗑️ Очистка старых постов...")
                deleted = await db_manager.cleanup_old_posts(
                    days=self.config.POSTS_RETENTION_DAYS
                )
                logger.info(f"✅ Удалено старых постов: {deleted}")
            except Exception as e:
                logger.error(f"❌ Ошибка очистки: {e}")
