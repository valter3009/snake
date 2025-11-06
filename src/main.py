"""
Главная точка входа в приложение.

Инициализирует все компоненты и запускает бота.
"""

import asyncio
import signal
import sys
from pathlib import Path

# Добавляем src в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from utils.logger import setup_logger
from database.models import init_database
from database.db_manager import DatabaseManager
from collectors.market_collector import MarketCollector
from collectors.fear_greed_collector import FearGreedCollector
from filters.importance_scorer import ImportanceScorer
from ai.content_generator import ContentGenerator
from bot.channel_poster import TelegramPublisher
from bot.message_queue import MessageQueue
from schedulers.task_scheduler import TaskScheduler

logger = setup_logger('crypto_bot', level=config.log.level, log_dir=config.log.log_dir)


class CryptoBot:
    """
    Главный класс криптовалютного бота.

    Управляет жизненным циклом всех компонентов.
    """

    def __init__(self):
        """Инициализирует бота и все его компоненты."""
        logger.info("\n" + "=" * 70)
        logger.info("🚀 ЗАПУСК КРИПТОВАЛЮТНОГО AI TELEGRAM-БОТА")
        logger.info("=" * 70)

        # Проверяем конфигурацию
        if not config.validate():
            logger.error("❌ Конфигурация невалидна! Проверьте .env файл")
            sys.exit(1)

        # Выводим конфигурацию
        config.print_config()

        # Инициализируем базу данных
        logger.info("💾 Инициализация базы данных...")
        self.engine, SessionMaker = init_database(config.database.url)
        self.db_session = SessionMaker()
        self.db_manager = DatabaseManager(self.db_session)
        logger.info("✅ База данных готова")

        # Инициализируем коллекторы
        logger.info("📡 Инициализация коллекторов данных...")
        self.market_collector = MarketCollector()
        self.fear_greed_collector = FearGreedCollector()
        logger.info("✅ Коллекторы готовы")

        # Инициализируем фильтры
        logger.info("🔍 Инициализация системы фильтрации...")
        self.importance_scorer = ImportanceScorer()
        logger.info("✅ Система фильтрации готова")

        # Инициализируем AI генерацию
        logger.info("🧠 Инициализация AI генерации контента...")
        self.content_generator = ContentGenerator()
        logger.info("✅ AI генератор готов")

        # Инициализируем Telegram
        logger.info("📱 Инициализация Telegram...")
        self.telegram_publisher = TelegramPublisher()
        self.message_queue = MessageQueue(self.db_manager, self.telegram_publisher)
        logger.info("✅ Telegram готов")

        # Инициализируем планировщик
        logger.info("⏰ Инициализация планировщика задач...")
        self.scheduler = TaskScheduler(
            market_collector=self.market_collector,
            fear_greed_collector=self.fear_greed_collector,
            message_queue=self.message_queue,
            importance_scorer=self.importance_scorer,
            content_generator=self.content_generator
        )
        logger.info("✅ Планировщик готов")

        # Флаг для graceful shutdown
        self.running = False

        logger.info("\n" + "=" * 70)
        logger.info("✅ ВСЕ КОМПОНЕНТЫ ИНИЦИАЛИЗИРОВАНЫ")
        logger.info("=" * 70 + "\n")

    async def start(self):
        """Запускает бота."""
        logger.info("🎯 Запуск бота...")

        # Проверяем подключение к Telegram
        telegram_ok = await self.telegram_publisher.test_connection()
        if not telegram_ok:
            logger.error("❌ Не удалось подключиться к Telegram! Проверьте токен.")
            return

        # Получаем информацию о канале
        channel_info = await self.telegram_publisher.get_chat_info()
        if channel_info:
            logger.info(f"📢 Канал: {channel_info.get('title')} (@{channel_info.get('username')})")

        # Запускаем планировщик
        self.scheduler.start()

        # Устанавливаем флаг
        self.running = True

        logger.info("\n" + "=" * 70)
        logger.info("✅ БОТ УСПЕШНО ЗАПУЩЕН И РАБОТАЕТ!")
        logger.info("=" * 70)
        logger.info("Нажмите Ctrl+C для остановки\n")

        # Основной цикл
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Получен сигнал остановки...")

    async def stop(self):
        """Останавливает бота."""
        logger.info("\n" + "=" * 70)
        logger.info("🛑 ОСТАНОВКА БОТА...")
        logger.info("=" * 70)

        self.running = False

        # Останавливаем планировщик
        logger.info("Остановка планировщика...")
        self.scheduler.stop()

        # Закрываем HTTP клиенты
        logger.info("Закрытие HTTP соединений...")
        from utils.http_client import http_client
        await http_client.close()

        # Закрываем БД сессию
        logger.info("Закрытие БД...")
        self.db_session.close()

        logger.info("\n" + "=" * 70)
        logger.info("✅ БОТ ОСТАНОВЛЕН")
        logger.info("=" * 70 + "\n")

    def handle_signal(self, sig, frame):
        """Обработчик сигналов для graceful shutdown."""
        logger.info(f"\nПолучен сигнал {sig}, останавливаем бота...")
        asyncio.create_task(self.stop())


async def main():
    """Главная функция."""
    bot = CryptoBot()

    # Регистрируем обработчики сигналов для graceful shutdown
    signal.signal(signal.SIGINT, bot.handle_signal)
    signal.signal(signal.SIGTERM, bot.handle_signal)

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("\nПолучен Ctrl+C, останавливаем...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем")
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}", exc_info=True)
        sys.exit(1)
