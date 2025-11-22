"""
База данных с поддержкой PostgreSQL (asyncpg) и SQLite (aiosqlite)
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, select, delete
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base
from bot.core.logger import get_logger
from bot.core.exceptions import DatabaseError

logger = get_logger(__name__)

# Базовый класс для моделей
Base = declarative_base()


class PublishedPost(Base):
    """Модель опубликованного поста"""
    __tablename__ = 'published_posts'

    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    published_at = Column(DateTime, nullable=False)
    source = Column(String(100))
    telegram_message_id = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<PublishedPost(id={self.id}, title='{self.title[:50]}...', source='{self.source}')>"


class DatabaseManager:
    """
    Менеджер базы данных (ТОЛЬКО асинхронные операции с asyncpg)
    """

    def __init__(self, database_url: str):
        """
        Инициализация менеджера БД

        Args:
            database_url: URL базы данных PostgreSQL
        """
        self.database_url = database_url
        self.async_engine: Optional[AsyncEngine] = None
        self.async_session_maker: Optional[async_sessionmaker] = None

        logger.info("🔧 Инициализация DatabaseManager...")

    async def init_db(self) -> None:
        """
        Инициализация базы данных и создание таблиц
        """
        try:
            # Создаем async engine для асинхронной работы
            database_url = self.database_url

            # Поддержка PostgreSQL через asyncpg
            if database_url.startswith('postgresql://'):
                database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
            # Поддержка SQLite через aiosqlite
            elif database_url.startswith('sqlite://'):
                # Поддержка обоих форматов: sqlite:// и sqlite:///
                if database_url.startswith('sqlite:///'):
                    database_url = database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
                else:
                    database_url = database_url.replace('sqlite://', 'sqlite+aiosqlite:///')

            # Настройки для разных БД
            engine_kwargs = {'echo': False}
            if database_url.startswith('postgresql+asyncpg://'):
                engine_kwargs.update({
                    'pool_pre_ping': True,
                    'pool_size': 10,
                    'max_overflow': 20
                })

            self.async_engine = create_async_engine(database_url, **engine_kwargs)

            # Создаем фабрику async сессий
            self.async_session_maker = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # Создаем таблицы
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("✅ База данных инициализирована успешно")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            raise DatabaseError(f"Не удалось инициализировать базу данных: {e}")

    async def is_post_published(self, url: str) -> bool:
        """
        Проверить, был ли уже опубликован пост с данным URL

        Args:
            url: URL новости

        Returns:
            True если пост уже был опубликован, иначе False
        """
        if not self.async_session_maker:
            logger.warning("⚠️ DatabaseManager не инициализирован")
            return False

        try:
            async with self.async_session_maker() as session:
                stmt = select(PublishedPost).where(PublishedPost.url == url)
                result = await session.execute(stmt)
                post = result.scalar_one_or_none()
                return post is not None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки публикации поста: {e}")
            return False

    async def add_published_post(
        self,
        url: str,
        title: str,
        published_at: datetime,
        source: str,
        telegram_message_id: Optional[int] = None
    ) -> bool:
        """
        Добавить информацию об опубликованном посте

        Args:
            url: URL новости
            title: Заголовок
            published_at: Дата публикации
            source: Источник новости
            telegram_message_id: ID сообщения в Telegram

        Returns:
            True если пост добавлен успешно, иначе False
        """
        if not self.async_session_maker:
            logger.warning("⚠️ DatabaseManager не инициализирован")
            return False

        try:
            async with self.async_session_maker() as session:
                post = PublishedPost(
                    url=url,
                    title=title,
                    published_at=published_at,
                    source=source,
                    telegram_message_id=telegram_message_id
                )
                session.add(post)
                await session.commit()

                logger.info(f"✅ Пост добавлен в БД: {title[:50]}...")
                return True

        except Exception as e:
            logger.error(f"❌ Ошибка добавления поста в БД: {e}")
            return False

    async def get_today_published_count(self) -> int:
        """
        Получить количество опубликованных постов за сегодня

        Returns:
            Количество постов
        """
        if not self.async_session_maker:
            logger.warning("⚠️ DatabaseManager не инициализирован")
            return 0

        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

            async with self.async_session_maker() as session:
                stmt = select(PublishedPost).where(
                    PublishedPost.created_at >= today_start
                )
                result = await session.execute(stmt)
                posts = result.scalars().all()
                return len(posts)

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики за день: {e}")
            return 0

    async def cleanup_old_posts(self, days: int = 30) -> int:
        """
        Удалить старые посты из базы данных

        Args:
            days: Количество дней для хранения постов

        Returns:
            Количество удаленных постов
        """
        if not self.async_session_maker:
            logger.warning("⚠️ DatabaseManager не инициализирован")
            return 0

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.async_session_maker() as session:
                stmt = delete(PublishedPost).where(
                    PublishedPost.created_at < cutoff_date
                )
                result = await session.execute(stmt)
                await session.commit()

                deleted_count = result.rowcount
                if deleted_count > 0:
                    logger.info(f"🗑️ Удалено {deleted_count} старых постов из БД")

                return deleted_count

        except Exception as e:
            logger.error(f"❌ Ошибка очистки старых постов: {e}")
            return 0

    async def get_recent_posts(self, limit: int = 100) -> List[PublishedPost]:
        """
        Получить последние опубликованные посты

        Args:
            limit: Максимальное количество постов

        Returns:
            Список постов
        """
        if not self.async_session_maker:
            logger.warning("⚠️ DatabaseManager не инициализирован")
            return []

        try:
            async with self.async_session_maker() as session:
                stmt = select(PublishedPost).order_by(
                    PublishedPost.created_at.desc()
                ).limit(limit)
                result = await session.execute(stmt)
                posts = result.scalars().all()
                return list(posts)

        except Exception as e:
            logger.error(f"❌ Ошибка получения последних постов: {e}")
            return []

    async def close(self) -> None:
        """
        Закрыть соединения с базой данных (graceful shutdown)
        """
        if self.async_engine:
            try:
                await self.async_engine.dispose()
                logger.info("✅ Соединения с БД закрыты успешно")
            except Exception as e:
                logger.error(f"❌ Ошибка при закрытии соединений с БД: {e}")


# Глобальный экземпляр менеджера БД (будет инициализирован в main.py)
db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> Optional[DatabaseManager]:
    """
    Получить глобальный экземпляр менеджера БД

    Returns:
        DatabaseManager или None если не инициализирован
    """
    return db_manager


async def init_database(database_url: str) -> DatabaseManager:
    """
    Инициализировать глобальный менеджер БД

    Args:
        database_url: URL базы данных

    Returns:
        Инициализированный DatabaseManager
    """
    global db_manager

    db_manager = DatabaseManager(database_url)
    await db_manager.init_db()

    return db_manager
