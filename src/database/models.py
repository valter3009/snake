"""
Модели базы данных для хранения событий и статистики.

Используем SQLAlchemy ORM для работы с БД.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class PublishedMessage(Base):
    """
    Таблица опубликованных сообщений - для дедупликации и статистики.

    Attributes:
        id: Уникальный идентификатор
        event_type: Тип события (whale, listing, market_overview, etc.)
        event_hash: Хэш события для дедупликации
        message_text: Текст опубликованного сообщения
        importance_score: Оценка важности (0-10)
        published_at: Время публикации
        telegram_message_id: ID сообщения в Telegram
    """

    __tablename__ = 'published_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False, index=True)
    event_hash = Column(String(64), nullable=False, unique=True, index=True)
    message_text = Column(Text, nullable=False)
    importance_score = Column(Float, nullable=False)
    published_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    telegram_message_id = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<PublishedMessage(id={self.id}, type={self.event_type}, score={self.importance_score})>"


class WhaleTransaction(Base):
    """
    Таблица движений китов - для отслеживания крупных транзакций.

    Attributes:
        id: Уникальный идентификатор
        tx_hash: Хэш транзакции
        symbol: Символ криптовалюты (BTC, ETH, etc.)
        amount_crypto: Количество криптовалюты
        amount_usd: Сумма в USD
        from_address: Адрес отправителя
        to_address: Адрес получателя
        from_owner: Владелец адреса отправителя (биржа/неизвестно)
        to_owner: Владелец адреса получателя
        blockchain: Название блокчейна
        detected_at: Время обнаружения транзакции
        published: Опубликовано ли сообщение
    """

    __tablename__ = 'whale_transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_hash = Column(String(128), nullable=False, unique=True, index=True)
    symbol = Column(String(10), nullable=False)
    amount_crypto = Column(Float, nullable=False)
    amount_usd = Column(Float, nullable=False, index=True)
    from_address = Column(String(128), nullable=False)
    to_address = Column(String(128), nullable=False)
    from_owner = Column(String(100), nullable=True)
    to_owner = Column(String(100), nullable=True)
    blockchain = Column(String(50), nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    published = Column(Boolean, default=False)

    def __repr__(self):
        return f"<WhaleTransaction(symbol={self.symbol}, amount=${self.amount_usd:,.0f})>"


class ListingEvent(Base):
    """
    Таблица новых листингов на биржах.

    Attributes:
        id: Уникальный идентификатор
        exchange: Название биржи (Binance, Coinbase, etc.)
        symbol: Символ криптовалюты
        name: Полное название проекта
        listing_date: Дата листинга
        market_cap: Рыночная капитализация
        category: Категория проекта (Layer1, DeFi, etc.)
        detected_at: Время обнаружения листинга
        published: Опубликовано ли
    """

    __tablename__ = 'listing_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(10), nullable=False)
    name = Column(String(100), nullable=False)
    listing_date = Column(DateTime, nullable=False)
    market_cap = Column(Float, nullable=True)
    category = Column(String(50), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    published = Column(Boolean, default=False)

    def __repr__(self):
        return f"<ListingEvent(exchange={self.exchange}, symbol={self.symbol})>"


class FearGreedIndex(Base):
    """
    Таблица значений индекса страха и жадности.

    Attributes:
        id: Уникальный идентификатор
        value: Значение индекса (0-100)
        classification: Классификация (Extreme Fear, Fear, Neutral, Greed, Extreme Greed)
        recorded_at: Время записи
        published: Опубликовано ли изменение
    """

    __tablename__ = 'fear_greed_index'

    id = Column(Integer, primary_key=True, autoincrement=True)
    value = Column(Integer, nullable=False)
    classification = Column(String(50), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    published = Column(Boolean, default=False)

    def __repr__(self):
        return f"<FearGreedIndex(value={self.value}, classification={self.classification})>"


class PublicationStats(Base):
    """
    Таблица статистики публикаций - для контроля лимитов.

    Attributes:
        id: Уникальный идентификатор
        date: Дата
        hour: Час (0-23)
        messages_count: Количество сообщений за этот час
        last_message_time: Время последнего сообщения
    """

    __tablename__ = 'publication_stats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)
    hour = Column(Integer, nullable=False)
    messages_count = Column(Integer, default=0)
    last_message_time = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<PublicationStats(date={self.date}, hour={self.hour}, count={self.messages_count})>"


def init_database(database_url: str):
    """
    Инициализирует базу данных и создает все таблицы.

    Args:
        database_url: URL базы данных (SQLite или PostgreSQL)

    Returns:
        tuple: (engine, SessionMaker)

    Example:
        >>> engine, Session = init_database('sqlite:///./test.db')
        >>> session = Session()
        >>> # Работаем с сессией
        >>> session.close()
    """
    # Создаем engine
    engine = create_engine(
        database_url,
        echo=False,  # Не выводим SQL запросы в консоль
        pool_pre_ping=True,  # Проверяем соединение перед использованием
    )

    # Создаем все таблицы
    Base.metadata.create_all(engine)

    # Создаем фабрику сессий
    SessionMaker = sessionmaker(bind=engine)

    return engine, SessionMaker
