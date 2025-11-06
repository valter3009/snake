"""
Менеджер базы данных - CRUD операции и бизнес-логика работы с БД.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from database.models import (
    PublishedMessage,
    WhaleTransaction,
    ListingEvent,
    FearGreedIndex,
    PublicationStats
)
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    Управляет всеми операциями с базой данных.

    Provides методы для:
    - Проверки дубликатов событий
    - Сохранения опубликованных сообщений
    - Получения статистики
    - Контроля лимитов публикаций
    """

    def __init__(self, session: Session):
        """
        Инициализирует менеджер БД.

        Args:
            session: Активная SQLAlchemy сессия
        """
        self.session = session

    def generate_event_hash(self, event_type: str, event_data: dict) -> str:
        """
        Генерирует уникальный хэш для события для дедупликации.

        Args:
            event_type: Тип события (whale, listing, etc.)
            event_data: Данные события

        Returns:
            str: SHA256 хэш события

        Example:
            >>> data = {'symbol': 'BTC', 'amount': 5000000}
            >>> hash_val = db.generate_event_hash('whale', data)
            >>> len(hash_val)
            64
        """
        # Создаем строку из ключевых данных события
        if event_type == 'whale':
            unique_string = f"{event_type}:{event_data.get('tx_hash', '')}"
        elif event_type == 'listing':
            unique_string = f"{event_type}:{event_data.get('exchange', '')}:{event_data.get('symbol', '')}"
        elif event_type == 'market_overview':
            # Рыночный обзор уникален по дате
            date_str = event_data.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
            time_str = event_data.get('time', 'morning')
            unique_string = f"{event_type}:{date_str}:{time_str}"
        else:
            # Общий случай
            unique_string = f"{event_type}:{str(event_data)}"

        # Генерируем SHA256 хэш
        return hashlib.sha256(unique_string.encode()).hexdigest()

    def is_duplicate_event(self, event_hash: str) -> bool:
        """
        Проверяет существует ли уже событие с таким хэшем.

        Args:
            event_hash: Хэш события

        Returns:
            bool: True если дубликат, False если новое

        Example:
            >>> if not db.is_duplicate_event(event_hash):
            ...     # Публикуем новое событие
            ...     pass
        """
        exists = self.session.query(PublishedMessage).filter_by(event_hash=event_hash).first()
        return exists is not None

    def save_published_message(
        self,
        event_type: str,
        event_hash: str,
        message_text: str,
        importance_score: float,
        telegram_message_id: Optional[int] = None
    ) -> PublishedMessage:
        """
        Сохраняет опубликованное сообщение в БД.

        Args:
            event_type: Тип события
            event_hash: Хэш события
            message_text: Текст сообщения
            importance_score: Оценка важности
            telegram_message_id: ID сообщения в Telegram

        Returns:
            PublishedMessage: Сохраненная запись
        """
        message = PublishedMessage(
            event_type=event_type,
            event_hash=event_hash,
            message_text=message_text,
            importance_score=importance_score,
            telegram_message_id=telegram_message_id,
            published_at=datetime.utcnow()
        )

        self.session.add(message)
        self.session.commit()

        logger.info(f"✅ Сохранено сообщение: {event_type} (score: {importance_score:.1f})")
        return message

    def save_whale_transaction(self, tx_data: dict) -> WhaleTransaction:
        """
        Сохраняет транзакцию кита в БД.

        Args:
            tx_data: Данные транзакции

        Returns:
            WhaleTransaction: Сохраненная запись
        """
        transaction = WhaleTransaction(
            tx_hash=tx_data['tx_hash'],
            symbol=tx_data['symbol'],
            amount_crypto=tx_data['amount_crypto'],
            amount_usd=tx_data['amount_usd'],
            from_address=tx_data['from_address'],
            to_address=tx_data['to_address'],
            from_owner=tx_data.get('from_owner'),
            to_owner=tx_data.get('to_owner'),
            blockchain=tx_data['blockchain'],
            published=False
        )

        self.session.add(transaction)
        self.session.commit()

        return transaction

    def get_messages_count_today(self) -> int:
        """
        Возвращает количество сообщений опубликованных сегодня.

        Returns:
            int: Количество сообщений
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        count = self.session.query(PublishedMessage).filter(
            PublishedMessage.published_at >= today_start
        ).count()

        return count

    def get_messages_count_current_hour(self) -> int:
        """
        Возвращает количество сообщений опубликованных в текущий час.

        Returns:
            int: Количество сообщений
        """
        hour_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

        count = self.session.query(PublishedMessage).filter(
            PublishedMessage.published_at >= hour_start
        ).count()

        return count

    def get_last_message_time(self) -> Optional[datetime]:
        """
        Возвращает время последнего опубликованного сообщения.

        Returns:
            datetime или None: Время последнего сообщения
        """
        last_message = self.session.query(PublishedMessage).order_by(
            PublishedMessage.published_at.desc()
        ).first()

        return last_message.published_at if last_message else None

    def get_last_fear_greed_value(self) -> Optional[int]:
        """
        Возвращает последнее значение индекса страха/жадности.

        Returns:
            int или None: Последнее значение индекса
        """
        last_record = self.session.query(FearGreedIndex).order_by(
            FearGreedIndex.recorded_at.desc()
        ).first()

        return last_record.value if last_record else None

    def save_fear_greed_index(self, value: int, classification: str) -> FearGreedIndex:
        """
        Сохраняет значение индекса страха/жадности.

        Args:
            value: Значение индекса (0-100)
            classification: Классификация (Extreme Fear, etc.)

        Returns:
            FearGreedIndex: Сохраненная запись
        """
        record = FearGreedIndex(
            value=value,
            classification=classification,
            recorded_at=datetime.utcnow(),
            published=False
        )

        self.session.add(record)
        self.session.commit()

        return record

    def get_recent_messages(self, limit: int = 10) -> List[PublishedMessage]:
        """
        Возвращает последние опубликованные сообщения.

        Args:
            limit: Максимальное количество сообщений

        Returns:
            List[PublishedMessage]: Список сообщений
        """
        messages = self.session.query(PublishedMessage).order_by(
            PublishedMessage.published_at.desc()
        ).limit(limit).all()

        return messages

    def get_stats_summary(self) -> dict:
        """
        Возвращает сводную статистику работы бота.

        Returns:
            dict: Словарь со статистикой
        """
        total_messages = self.session.query(PublishedMessage).count()
        today_messages = self.get_messages_count_today()
        hour_messages = self.get_messages_count_current_hour()

        # Статистика по типам событий
        whale_count = self.session.query(PublishedMessage).filter_by(event_type='whale').count()
        listing_count = self.session.query(PublishedMessage).filter_by(event_type='listing').count()
        market_count = self.session.query(PublishedMessage).filter_by(event_type='market_overview').count()

        # Средняя оценка важности
        avg_score = self.session.query(PublishedMessage).with_entities(
            PublishedMessage.importance_score
        ).all()
        avg_importance = sum(s[0] for s in avg_score) / len(avg_score) if avg_score else 0

        return {
            'total_messages': total_messages,
            'today_messages': today_messages,
            'hour_messages': hour_messages,
            'whale_alerts': whale_count,
            'listing_alerts': listing_count,
            'market_overviews': market_count,
            'avg_importance_score': round(avg_importance, 2)
        }

    def cleanup_old_records(self, days: int = 30):
        """
        Удаляет старые записи из БД для экономии места.

        Args:
            days: Сколько дней хранить записи

        Example:
            >>> db.cleanup_old_records(days=30)  # Удалить записи старше 30 дней
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Удаляем старые опубликованные сообщения
        deleted_messages = self.session.query(PublishedMessage).filter(
            PublishedMessage.published_at < cutoff_date
        ).delete()

        # Удаляем старые транзакции китов
        deleted_whales = self.session.query(WhaleTransaction).filter(
            WhaleTransaction.detected_at < cutoff_date
        ).delete()

        self.session.commit()

        logger.info(f"🗑️ Очищено {deleted_messages} сообщений и {deleted_whales} транзакций")
