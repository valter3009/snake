"""
Очередь сообщений с контролем лимитов публикаций.

Управляет частотой публикаций: не более 3/час и 12/день.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass
from utils.logger import get_logger
from config import config

logger = get_logger(__name__)


@dataclass
class QueuedMessage:
    """Сообщение в очереди."""
    message_text: str
    importance_score: float
    event_type: str
    event_hash: str
    timestamp: datetime


class MessageQueue:
    """
    Управляет очередью сообщений и контролирует лимиты публикаций.

    Features:
    - Приоритетная очередь по важности
    - Лимиты: 3 сообщения в час, 12 в день
    - Минимальный интервал между сообщениями: 10 минут
    - Автоматическая публикация когда возможно
    """

    def __init__(self, db_manager, telegram_publisher):
        """
        Инициализирует очередь сообщений.

        Args:
            db_manager: Менеджер базы данных
            telegram_publisher: Публикатор в Telegram
        """
        self.db = db_manager
        self.publisher = telegram_publisher
        self.queue: List[QueuedMessage] = []

        # Лимиты из конфигурации
        self.max_per_hour = config.rate_limit.max_messages_per_hour
        self.max_per_day = config.rate_limit.max_messages_per_day
        self.min_interval_seconds = config.rate_limit.min_interval_seconds

        logger.info(f"MessageQueue: лимиты {self.max_per_hour}/час, {self.max_per_day}/день")

    async def add_message(
        self,
        message_text: str,
        importance_score: float,
        event_type: str,
        event_hash: str
    ):
        """
        Добавляет сообщение в очередь с приоритетом по важности.

        Args:
            message_text: Текст сообщения
            importance_score: Оценка важности (0-10)
            event_type: Тип события
            event_hash: Хэш события для дедупликации
        """
        # Проверяем дубликаты
        if self.db.is_duplicate_event(event_hash):
            logger.info(f"⏭️ Сообщение уже опубликовано (hash: {event_hash[:8]}...)")
            return

        # Создаем сообщение для очереди
        queued_msg = QueuedMessage(
            message_text=message_text,
            importance_score=importance_score,
            event_type=event_type,
            event_hash=event_hash,
            timestamp=datetime.utcnow()
        )

        # Добавляем в очередь
        self.queue.append(queued_msg)

        # Сортируем по важности (самые важные первыми)
        self.queue.sort(key=lambda x: x.importance_score, reverse=True)

        logger.info(
            f"➕ Добавлено в очередь: {event_type} "
            f"(важность: {importance_score:.1f}, в очереди: {len(self.queue)})"
        )

        # Пытаемся сразу опубликовать
        await self.try_publish_next()

    async def try_publish_next(self):
        """
        Пытается опубликовать следующее сообщение из очереди.

        Проверяет все лимиты перед публикацией.
        """
        if not self.queue:
            return

        # Проверяем дневной лимит
        messages_today = self.db.get_messages_count_today()
        if messages_today >= self.max_per_day:
            logger.warning(f"⚠️ Достигнут дневной лимит: {messages_today}/{self.max_per_day}")
            return

        # Проверяем почасовой лимит
        messages_hour = self.db.get_messages_count_current_hour()
        if messages_hour >= self.max_per_hour:
            logger.warning(f"⚠️ Достигнут почасовой лимит: {messages_hour}/{self.max_per_hour}")
            return

        # Проверяем минимальный интервал
        last_message_time = self.db.get_last_message_time()
        if last_message_time:
            time_since_last = (datetime.utcnow() - last_message_time).total_seconds()
            if time_since_last < self.min_interval_seconds:
                wait_time = self.min_interval_seconds - time_since_last
                logger.info(f"⏳ Ожидание {wait_time:.0f}с до следующего сообщения")
                return

        # Все проверки пройдены - публикуем!
        msg = self.queue.pop(0)
        await self._publish_message(msg)

    async def _publish_message(self, msg: QueuedMessage):
        """
        Публикует сообщение в Telegram и сохраняет в БД.

        Args:
            msg: Сообщение для публикации
        """
        try:
            # Публикуем в Telegram
            telegram_msg_id = await self.publisher.send_message(msg.message_text)

            # Сохраняем в БД
            self.db.save_published_message(
                event_type=msg.event_type,
                event_hash=msg.event_hash,
                message_text=msg.message_text,
                importance_score=msg.importance_score,
                telegram_message_id=telegram_msg_id
            )

            logger.info(
                f"✅ Опубликовано: {msg.event_type} "
                f"(важность: {msg.importance_score:.1f}, в очереди: {len(self.queue)})"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}", exc_info=True)
            # Возвращаем сообщение в очередь
            self.queue.insert(0, msg)

    async def process_queue_periodically(self):
        """
        Периодически проверяет очередь и публикует сообщения.

        Запускается как фоновая задача.
        """
        logger.info("🔄 Запущена периодическая обработка очереди")

        while True:
            try:
                await self.try_publish_next()
                await asyncio.sleep(60)  # Проверяем каждую минуту

            except Exception as e:
                logger.error(f"Ошибка в process_queue: {e}", exc_info=True)
                await asyncio.sleep(60)

    def get_queue_status(self) -> Dict:
        """
        Возвращает статус очереди.

        Returns:
            Dict: Статус очереди
        """
        messages_today = self.db.get_messages_count_today()
        messages_hour = self.db.get_messages_count_current_hour()
        last_message = self.db.get_last_message_time()

        return {
            'queue_length': len(self.queue),
            'messages_today': messages_today,
            'messages_hour': messages_hour,
            'daily_limit': self.max_per_day,
            'hourly_limit': self.max_per_hour,
            'last_message_time': last_message.isoformat() if last_message else None,
        }

    def clear_old_messages(self, max_age_hours: int = 24):
        """
        Удаляет старые сообщения из очереди.

        Args:
            max_age_hours: Максимальный возраст сообщения в часах
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        original_count = len(self.queue)

        self.queue = [
            msg for msg in self.queue
            if msg.timestamp > cutoff_time
        ]

        removed = original_count - len(self.queue)
        if removed > 0:
            logger.info(f"🗑️ Удалено {removed} старых сообщений из очереди")
