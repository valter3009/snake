"""
Планировщик публикаций постов
"""
import logging
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional
from io import BytesIO

from telegram import Bot
from telegram.error import TelegramError

import bot.config
import bot.news_collector
import bot.news_analyzer
import bot.post_generator
import bot.moderator
import bot.media_handler
import bot.database
from bot.post_generator import TelegramPost

logger = logging.getLogger(__name__)


class NewsScheduler:
    """Планировщик сбора и публикации новостей"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.is_running = False
        self.collection_task = None
        self.cleanup_task = None

    async def start(self):
        """Запуск планировщика"""
        if self.is_running:
            logger.warning("Планировщик уже запущен")
            return

        self.is_running = True
        logger.info("Запуск планировщика...")

        # Запускаем задачи
        self.collection_task = asyncio.create_task(self._collection_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Планировщик запущен")

    async def stop(self):
        """Остановка планировщика"""
        if not self.is_running:
            return

        logger.info("Остановка планировщика...")
        self.is_running = False

        # Отменяем задачи
        if self.collection_task:
            self.collection_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()

        logger.info("Планировщик остановлен")

    async def _collection_loop(self):
        """Цикл сбора новостей"""
        while self.is_running:
            try:
                # Проверяем, нужно ли собирать новости
                if await self._should_collect_news():
                    logger.info("Начинаем цикл сбора новостей...")
                    await self._collect_and_publish_news()

                # Рандомный интервал между сборами
                interval = random.randint(
                    bot.config.config.MIN_COLLECTION_INTERVAL * 60,
                    bot.config.config.MAX_COLLECTION_INTERVAL * 60
                )
                logger.info(f"Следующий сбор новостей через {interval // 60} минут")
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле сбора новостей: {e}")
                # Ждём 5 минут перед повтором при ошибке
                await asyncio.sleep(300)

    async def _cleanup_loop(self):
        """Цикл очистки старых записей в БД"""
        while self.is_running:
            try:
                # Очищаем раз в день
                await bot.database.db_manager.cleanup_old_posts()
                await asyncio.sleep(86400)  # 24 часа

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле очистки: {e}")
                await asyncio.sleep(3600)  # Повтор через час при ошибке

    async def _should_collect_news(self) -> bool:
        """
        Проверка, нужно ли собирать новости сейчас

        Returns:
            True если нужно собирать новости
        """
        # Проверяем текущее время (по МСК)
        now = datetime.now(bot.config.config.TIMEZONE)
        current_hour = now.hour

        # Проверяем, что время в диапазоне публикаций
        if current_hour < bot.config.config.PUBLISH_START_HOUR or current_hour >= bot.config.config.PUBLISH_END_HOUR:
            logger.info(f"Время {current_hour}:00 вне диапазона публикаций ({bot.config.config.PUBLISH_START_HOUR}:00-{bot.config.config.PUBLISH_END_HOUR}:00)")
            return False

        # Проверяем, не превысили ли мы лимит постов за день
        today_count = await bot.database.db_manager.get_today_published_count()
        daily_limit = random.randint(bot.config.config.MIN_POSTS_PER_DAY, bot.config.config.MAX_POSTS_PER_DAY)

        if today_count >= daily_limit:
            logger.info(f"Достигнут дневной лимит постов: {today_count}/{daily_limit}")
            return False

        return True

    async def _collect_and_publish_news(self):
        """Сбор и публикация новостей"""
        try:
            # 1. Собираем новости
            logger.info("Собираем новости...")
            news_list = await bot.news_collector.news_collector.collect_news()

            if not news_list:
                logger.warning("Не удалось собрать новости")
                return

            # 2. Анализируем и ранжируем новости
            logger.info("Анализируем новости...")
            top_news = await bot.news_analyzer.news_analyzer.analyze_and_rank_news(news_list)

            if not top_news:
                logger.warning("Не удалось выбрать топовые новости")
                return

            # 3. Генерируем посты
            logger.info(f"Генерируем {len(top_news)} постов...")
            posts = await bot.post_generator.post_generator.generate_multiple_posts(top_news)

            if not posts:
                logger.warning("Не удалось сгенерировать посты")
                return

            # 4. Публикуем посты через модерацию
            for i, post in enumerate(posts):
                logger.info(f"Публикуем пост {i + 1}/{len(posts)}...")
                success = await self._publish_post_with_moderation(post)

                if success:
                    # Небольшая пауза между публикациями
                    if i < len(posts) - 1:
                        delay = random.randint(60, 300)  # 1-5 минут
                        logger.info(f"Пауза {delay} секунд перед следующим постом")
                        await asyncio.sleep(delay)

            logger.info("Цикл публикации завершён")

        except Exception as e:
            logger.error(f"Ошибка при сборе и публикации новостей: {e}")

    async def _publish_post_with_moderation(self, post: TelegramPost) -> bool:
        """
        Публикация поста через модерацию

        Args:
            post: Пост для публикации

        Returns:
            True если пост был опубликован
        """
        try:
            # Отправляем на модерацию
            moderation_result = await bot.moderator.moderator.submit_for_moderation(post)

            if not moderation_result.approved:
                logger.info("Пост отклонён модератором")
                return False

            # Используем отредактированный текст если есть
            final_text = moderation_result.edited_text or post.text

            # Публикуем в канал (передаём список изображений)
            success = await self._publish_to_channel(final_text, post.image_urls)

            if success:
                # Сохраняем в БД
                await bot.database.db_manager.add_published_post(
                    url=post.news_url,
                    title=final_text[:200],  # Сохраняем начало поста как заголовок
                    source=post.source
                )
                logger.info("Пост успешно опубликован")
                return True

            return False

        except Exception as e:
            logger.error(f"Ошибка публикации поста: {e}")
            return False

    async def _publish_to_channel(self, text: str, image_urls: Optional[list] = None) -> bool:
        """
        Публикация поста в канал

        Args:
            text: Текст поста
            image_urls: Список URL изображений (опционально)

        Returns:
            True если публикация успешна
        """
        try:
            from telegram import InputMediaPhoto

            if not image_urls:
                # Публикуем текстовый пост
                await self.bot.send_message(
                    chat_id=bot.config.config.TELEGRAM_CHANNEL_ID,
                    text=text,
                    parse_mode='Markdown'
                )
                logger.info("Текстовый пост опубликован")
                return True

            # Скачиваем и оптимизируем все изображения
            photos = []
            for url in image_urls[:4]:  # Максимум 4 изображения
                try:
                    photo = await bot.media_handler.media_handler.download_and_optimize_image(url)
                    if photo:
                        photos.append(photo)
                except Exception as e:
                    logger.warning(f"Ошибка загрузки изображения {url}: {e}")

            if not photos:
                # Если не удалось загрузить ни одно фото, публикуем текст
                await self.bot.send_message(
                    chat_id=bot.config.config.TELEGRAM_CHANNEL_ID,
                    text=text,
                    parse_mode='Markdown'
                )
                logger.info("Пост опубликован без изображений")
                return True

            # Если одно изображение - обычный send_photo
            if len(photos) == 1:
                await self.bot.send_photo(
                    chat_id=bot.config.config.TELEGRAM_CHANNEL_ID,
                    photo=photos[0],
                    caption=text,
                    parse_mode='Markdown'
                )
                logger.info("Пост с 1 изображением опубликован")
            else:
                # Если несколько изображений - медиа-группа
                media_group = []
                for i, photo in enumerate(photos):
                    # Текст добавляем только к первому фото
                    caption = text if i == 0 else None
                    media_group.append(InputMediaPhoto(
                        media=photo,
                        caption=caption,
                        parse_mode='Markdown' if caption else None
                    ))

                await self.bot.send_media_group(
                    chat_id=bot.config.config.TELEGRAM_CHANNEL_ID,
                    media=media_group
                )
                logger.info(f"Медиа-группа из {len(photos)} изображений опубликована")

            return True

        except TelegramError as e:
            logger.error(f"Ошибка публикации в Telegram: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при публикации: {e}")
            return False

    async def publish_now(self):
        """Принудительная публикация (для тестирования)"""
        logger.info("Принудительная публикация...")
        await self._collect_and_publish_news()


# Глобальный объект планировщика
scheduler: Optional[NewsScheduler] = None


def init_scheduler(bot: Bot) -> NewsScheduler:
    """
    Инициализация глобального планировщика

    Args:
        bot: Объект Telegram Bot

    Returns:
        NewsScheduler
    """
    global scheduler
    scheduler = NewsScheduler(bot)
    return scheduler
