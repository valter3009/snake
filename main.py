"""
Главный модуль новостного бота для Telegram
Автоматическая публикация новостей по расписанию
"""

import asyncio
import logging
import random
import signal
import sys
from datetime import datetime
import schedule
import time

from config import POST_TIMES, LOG_LEVEL, LOG_FORMAT, LOG_FILE
from database import NewsDatabase
from news_parser import NewsParser
from ai_processor import AIProcessor
from telegram_bot import TelegramPublisher


# Настройка логирования
def setup_logging():
    """Настройка системы логирования"""
    # Создание форматтера
    formatter = logging.Formatter(LOG_FORMAT)

    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(formatter)

    # Файловый обработчик
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(formatter)

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return logging.getLogger(__name__)


logger = setup_logging()


class NewsBot:
    """Главный класс новостного бота"""

    def __init__(self):
        """Инициализация бота и всех компонентов"""
        logger.info("=" * 60)
        logger.info("Инициализация новостного бота")
        logger.info("=" * 60)

        try:
            self.db = NewsDatabase()
            self.parser = NewsParser()
            self.ai = AIProcessor()
            self.telegram = TelegramPublisher()
            self.is_running = True
            self.news_cache = []  # Кеш спарсенных новостей

            logger.info("Все компоненты успешно инициализированы")

        except Exception as e:
            logger.error(f"Ошибка инициализации компонентов: {e}")
            raise

    async def test_all_connections(self) -> bool:
        """
        Тестирование всех подключений

        Returns:
            True если все подключения работают
        """
        logger.info("Тестирование подключений...")

        try:
            # Тест Claude API
            logger.info("Тест Claude API...")
            claude_ok = self.ai.test_connection()

            # Тест Telegram
            logger.info("Тест Telegram API...")
            telegram_ok = await self.telegram.test_connection()

            if claude_ok and telegram_ok:
                logger.info("✓ Все подключения успешны")
                return True
            else:
                logger.error("✗ Некоторые подключения не работают")
                return False

        except Exception as e:
            logger.error(f"Ошибка тестирования подключений: {e}")
            return False

    def refresh_news_cache(self):
        """Обновление кеша новостей из всех источников"""
        logger.info("Обновление кеша новостей...")

        try:
            # Парсинг всех новостей
            all_news = self.parser.fetch_all_news()

            # Фильтрация уже опубликованных новостей
            fresh_news = []
            for news in all_news:
                if not self.db.is_news_published(news['title'], news['url']):
                    fresh_news.append(news)

            self.news_cache = fresh_news
            logger.info(f"Кеш обновлен: {len(self.news_cache)} новых новостей")

        except Exception as e:
            logger.error(f"Ошибка обновления кеша: {e}")

    async def publish_single_post(self):
        """Публикация одного поста"""
        logger.info("-" * 60)
        logger.info("Начало публикации нового поста")

        try:
            # Проверка кеша
            if not self.news_cache:
                logger.info("Кеш пуст, обновляем...")
                self.refresh_news_cache()

            if not self.news_cache:
                logger.warning("Нет доступных новостей для публикации")
                return

            # Выбор случайной новости
            news_item = random.choice(self.news_cache)
            self.news_cache.remove(news_item)

            logger.info(f"Выбрана новость: {news_item['title'][:60]}...")

            # Генерация поста через AI
            logger.info("Генерация текста поста через Claude...")
            post_data = self.ai.generate_post_text(news_item)

            if not post_data:
                logger.error("Не удалось сгенерировать текст поста")
                self.db.update_statistics(success=False)
                return

            # Форматирование поста
            post_text = self.ai.format_telegram_post(post_data, news_item['source'])
            logger.info(f"Пост сформирован:\n{post_text}")

            # Попытка извлечь медиа
            logger.info("Попытка извлечения изображения...")
            news_with_media = self.parser.get_news_with_media(news_item)

            # Публикация в Telegram
            logger.info("Публикация в Telegram...")
            message_id = await self.telegram.publish_post(
                text=post_text,
                image_data=news_with_media.get('media_data'),
                image_format=news_with_media.get('media_format')
            )

            if message_id:
                # Сохранение в базу данных
                self.db.add_published_news(
                    title=news_item['title'],
                    source=news_item['source'],
                    url=news_item['url'],
                    telegram_message_id=message_id,
                    has_media=bool(news_with_media.get('media_data'))
                )

                self.db.update_statistics(success=True)
                logger.info(f"✓ Пост успешно опубликован (ID: {message_id})")

                # Статистика
                today_count = self.db.get_published_count_today()
                logger.info(f"Опубликовано сегодня: {today_count}")

            else:
                logger.error("✗ Не удалось опубликовать пост")
                self.db.update_statistics(success=False)

        except Exception as e:
            logger.error(f"Ошибка при публикации поста: {e}")
            self.db.update_statistics(success=False)

    def scheduled_post(self):
        """Обертка для планировщика (синхронная функция)"""
        asyncio.run(self.publish_single_post())

    def setup_schedule(self):
        """Настройка расписания публикаций"""
        logger.info("Настройка расписания публикаций:")

        for post_time in POST_TIMES:
            schedule.every().day.at(post_time).do(self.scheduled_post)
            logger.info(f"  - Публикация в {post_time}")

        # Обновление кеша новостей каждые 2 часа
        schedule.every(2).hours.do(self.refresh_news_cache)
        logger.info("  - Обновление кеша новостей каждые 2 часа")

        # Очистка старых записей раз в день в 3:00
        schedule.every().day.at("03:00").do(lambda: self.db.cleanup_old_records(30))
        logger.info("  - Очистка старых записей в 03:00")

    def handle_shutdown(self, signum, frame):
        """Обработчик сигнала завершения"""
        logger.info("Получен сигнал завершения. Остановка бота...")
        self.is_running = False
        sys.exit(0)

    def run(self):
        """Запуск бота в режиме демона"""
        logger.info("=" * 60)
        logger.info("Запуск новостного бота")
        logger.info("=" * 60)

        # Регистрация обработчиков сигналов
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        # Тестирование подключений
        if not asyncio.run(self.test_all_connections()):
            logger.error("Не все подключения работают. Остановка.")
            sys.exit(1)

        # Первоначальное обновление кеша
        self.refresh_news_cache()

        # Настройка расписания
        self.setup_schedule()

        logger.info("Бот запущен и работает по расписанию")
        logger.info("Нажмите Ctrl+C для остановки")
        logger.info("=" * 60)

        # Основной цикл
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Проверка каждую минуту

            except KeyboardInterrupt:
                logger.info("Получено прерывание от клавиатуры")
                break
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                time.sleep(60)

        logger.info("Бот остановлен")


async def manual_test():
    """Ручной тест публикации одного поста"""
    logger.info("РЕЖИМ РУЧНОГО ТЕСТИРОВАНИЯ")
    logger.info("=" * 60)

    bot = NewsBot()

    # Тестирование подключений
    if not await bot.test_all_connections():
        logger.error("Тесты подключений не прошли")
        return

    # Публикация тестового поста
    await bot.publish_single_post()

    logger.info("=" * 60)
    logger.info("Тестирование завершено")


def main():
    """Главная функция"""
    import sys

    # Проверка аргументов командной строки
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Режим тестирования
        asyncio.run(manual_test())
    else:
        # Обычный режим работы
        bot = NewsBot()
        bot.run()


if __name__ == '__main__':
    main()
