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
        # Кэш последних опубликованных заголовков (для предотвращения дубликатов)
        self.recent_titles = []
        self.max_recent_titles = 50  # Храним последние 50 заголовков

        # Кэш последних использованных источников (для разнообразия)
        self.recent_sources = []
        self.max_recent_sources = 10  # Храним последние 10 источников

        # Счетчик публикаций по типам источников (для соотношения 2:1)
        self.recent_publications = []  # Список типов последних публикаций (True = international, False = russian)
        self.max_recent_publications = 30  # Храним последние 30 публикаций для анализа соотношения
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

    def _is_similar_title(self, title1: str, title2: str, threshold: float = 0.7) -> bool:
        """
        Проверить схожесть заголовков

        Args:
            title1: Первый заголовок
            title2: Второй заголовок
            threshold: Порог схожести (0.0 - 1.0)

        Returns:
            True если заголовки схожи
        """
        # Приводим к нижнему регистру и разбиваем на слова
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())

        # Убираем короткие слова (предлоги, союзы)
        words1 = {w for w in words1 if len(w) > 3}
        words2 = {w for w in words2 if len(w) > 3}

        if not words1 or not words2:
            return False

        # Вычисляем коэффициент Жаккара (пересечение / объединение)
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        similarity = intersection / union if union > 0 else 0

        return similarity >= threshold

    def _add_to_recent_titles(self, title: str):
        """
        Добавить заголовок в кэш последних заголовков

        Args:
            title: Заголовок новости
        """
        self.recent_titles.append(title)

        # Ограничиваем размер кэша
        if len(self.recent_titles) > self.max_recent_titles:
            self.recent_titles.pop(0)

    def _is_duplicate_news(self, title: str) -> bool:
        """
        Проверить, не является ли новость дубликатом

        Args:
            title: Заголовок новости

        Returns:
            True если новость является дубликатом
        """
        for recent_title in self.recent_titles:
            if self._is_similar_title(title, recent_title):
                return True
        return False

    def _add_to_recent_sources(self, source: str):
        """
        Добавить источник в кэш последних источников

        Args:
            source: Название источника
        """
        self.recent_sources.append(source)

        # Ограничиваем размер кэша
        if len(self.recent_sources) > self.max_recent_sources:
            self.recent_sources.pop(0)

    def _is_recent_source(self, source: str) -> bool:
        """
        Проверить, использовался ли источник недавно

        Args:
            source: Название источника

        Returns:
            True если источник использовался недавно
        """
        # Проверяем последние 3 источника (чтобы не было подряд одинаковых)
        recent_3 = self.recent_sources[-3:] if len(self.recent_sources) >= 3 else self.recent_sources
        return source in recent_3

    def _should_prefer_international(self) -> bool:
        """
        Определить, нужно ли предпочесть международную новость для соблюдения соотношения 2:1

        Returns:
            True если следующая новость должна быть международной
        """
        if len(self.recent_publications) < 3:
            # В начале предпочитаем российские
            return False

        # Подсчитываем соотношение за последние публикации
        recent = self.recent_publications[-9:]  # Берем последние 9 публикаций (3 цикла по соотношению 2:1)
        international_count = sum(1 for is_intl in recent if is_intl)
        russian_count = len(recent) - international_count

        # Если международных меньше 1/3, предпочитаем международную
        if len(recent) >= 3:
            expected_intl = len(recent) / 3
            return international_count < expected_intl

        return False

    def _add_to_recent_publications(self, is_international: bool):
        """
        Добавить публикацию в кэш последних публикаций

        Args:
            is_international: True если публикация международная
        """
        self.recent_publications.append(is_international)

        # Ограничиваем размер кэша
        if len(self.recent_publications) > self.max_recent_publications:
            self.recent_publications.pop(0)

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
            # Если нужен только 1 пост, отбираем больше новостей для выбора (с учетом дубликатов и повторов источников)
            top_count = 15 if single_post else self.config.TOP_NEWS_COUNT
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

            # Для single_post режима определяем, какой тип новости нужен
            prefer_international = self._should_prefer_international() if single_post else False
            if single_post:
                russian_count = sum(1 for n in top_news if not n.get('is_international', False))
                international_count = sum(1 for n in top_news if n.get('is_international', False))
                logger.info(f"  📊 Доступно: российских {russian_count}, международных {international_count}")
                logger.info(f"  🎯 Предпочтение: {'международная' if prefer_international else 'российская'} новость")

                # Сортируем новости по предпочтению
                if prefer_international and international_count > 0:
                    # Сначала международные, потом российские
                    top_news = sorted(top_news, key=lambda x: (not x.get('is_international', False)))
                elif not prefer_international and russian_count > 0:
                    # Сначала российские, потом международные
                    top_news = sorted(top_news, key=lambda x: x.get('is_international', False))

            for news_item in top_news:
                try:
                    title = news_item.get('title', '')
                    source = news_item.get('source', 'Unknown')
                    is_international = news_item.get('is_international', False)

                    # Проверяем на дубликаты
                    if self._is_duplicate_news(title):
                        logger.warning(f"  ⚠️ Пропускаем дубликат: {title[:50]}...")
                        continue

                    # Проверяем, не использовался ли источник недавно (только для single_post)
                    if single_post and self._is_recent_source(source):
                        logger.warning(f"  ⚠️ Пропускаем {source} - использовался недавно")
                        continue

                    # Извлекаем полный текст
                    url = news_item.get('url', '')
                    description = news_item.get('description', '')

                    full_text = await self.news_extractor.extract_with_fallback(url, description)

                    # Извлекаем видео (приоритет над изображением)
                    video_url = await self.news_extractor.extract_video_url(url)
                    if video_url:
                        news_item['video_url'] = video_url
                        logger.info(f"  🎥 Найдено видео для {title[:30]}...")

                    # Извлекаем изображение (если нет видео)
                    if not video_url:
                        image_url = await self.news_extractor.extract_image_url(url)
                        if image_url:
                            news_item['image_url'] = image_url
                            logger.info(f"  🖼️ Найдено изображение для {title[:30]}...")

                    # Генерируем пост
                    post = await self.content_generator.generate_post(news_item, full_text)

                    if post:
                        generated_posts.append((news_item, post))
                        stats['generated'] += 1
                        # Добавляем в кэш после успешной генерации
                        self._add_to_recent_titles(title)
                        self._add_to_recent_sources(source)
                        self._add_to_recent_publications(is_international)
                        news_type = "международная" if is_international else "российская"
                        logger.info(f"  ✅ Пост сгенерирован ({news_type}): {title[:50]}... (источник: {source})")

                        # Если нужен только 1 пост - прерываем цикл
                        if single_post:
                            break

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
