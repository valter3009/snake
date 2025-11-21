"""
Работа с базой данных PostgreSQL
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select

import bot.config

logger = logging.getLogger(__name__)

Base = declarative_base()


class PublishedPost(Base):
    """Модель опубликованного поста"""
    __tablename__ = 'published_posts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(500), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    published_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    source = Column(String(100))  # NewsAPI, RBC, TASS, etc.

    def __repr__(self):
        return f"<PublishedPost(id={self.id}, title='{self.title[:50]}...', published_at={self.published_at})>"


class PostSchedule(Base):
    """Модель расписания публикаций для статистики"""
    __tablename__ = 'post_schedule'

    id = Column(Integer, primary_key=True, autoincrement=True)
    scheduled_time = Column(DateTime, nullable=False)
    published = Column(Boolean, default=False)
    post_id = Column(Integer, nullable=True)  # ID в Telegram
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<PostSchedule(id={self.id}, scheduled_time={self.scheduled_time}, published={self.published})>"


class DatabaseManager:
    """Менеджер для работы с базой данных"""

    def __init__(self, database_url: str):
        """
        Инициализация менеджера БД

        Args:
            database_url: URL подключения к PostgreSQL
        """
        # Конвертируем postgres:// в postgresql:// для SQLAlchemy 1.4+
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

        # Создаем async engine для асинхронной работы (ТОЛЬКО asyncpg, БЕЗ psycopg2)
        self.async_engine = create_async_engine(
            database_url.replace('postgresql://', 'postgresql+asyncpg://'),
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )

        # Создаем фабрику async сессий
        self.async_session_maker = async_sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def init_db(self):
        """Инициализация базы данных (создание таблиц) - только async"""
        try:
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("База данных успешно инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise

    @asynccontextmanager
    async def get_session(self):
        """Получение асинхронной сессии БД"""
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def is_post_published(self, url: str) -> bool:
        """
        Проверка, был ли пост уже опубликован

        Args:
            url: URL новости

        Returns:
            True если пост уже был опубликован
        """
        async with self.get_session() as session:
            result = await session.execute(
                select(PublishedPost).where(PublishedPost.url == url)
            )
            return result.scalar_one_or_none() is not None

    async def add_published_post(self, url: str, title: str, source: str = None) -> PublishedPost:
        """
        Добавление опубликованного поста в БД

        Args:
            url: URL новости
            title: Заголовок новости
            source: Источник новости

        Returns:
            Объект PublishedPost
        """
        async with self.get_session() as session:
            post = PublishedPost(
                url=url,
                title=title,
                source=source,
                published_at=datetime.utcnow()
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)
            logger.info(f"Добавлен опубликованный пост: {title[:50]}...")
            return post

    async def get_published_posts(self, hours: int = 24) -> List[PublishedPost]:
        """
        Получение опубликованных постов за последние N часов

        Args:
            hours: Количество часов

        Returns:
            Список объектов PublishedPost
        """
        async with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            result = await session.execute(
                select(PublishedPost)
                .where(PublishedPost.published_at >= cutoff_time)
                .order_by(PublishedPost.published_at.desc())
            )
            return result.scalars().all()

    async def cleanup_old_posts(self):
        """Очистка старых постов (старше POSTS_RETENTION_DAYS)"""
        async with self.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=bot.config.config.POSTS_RETENTION_DAYS)
            result = await session.execute(
                select(PublishedPost).where(PublishedPost.published_at < cutoff_date)
            )
            old_posts = result.scalars().all()

            for post in old_posts:
                await session.delete(post)

            await session.commit()
            logger.info(f"Удалено {len(old_posts)} старых постов")

    async def add_schedule_entry(self, scheduled_time: datetime) -> PostSchedule:
        """
        Добавление записи в расписание

        Args:
            scheduled_time: Время публикации

        Returns:
            Объект PostSchedule
        """
        async with self.get_session() as session:
            schedule = PostSchedule(
                scheduled_time=scheduled_time,
                published=False
            )
            session.add(schedule)
            await session.commit()
            await session.refresh(schedule)
            return schedule

    async def mark_schedule_published(self, schedule_id: int, post_id: int = None):
        """
        Отметить запись расписания как опубликованную

        Args:
            schedule_id: ID записи расписания
            post_id: ID поста в Telegram
        """
        async with self.get_session() as session:
            result = await session.execute(
                select(PostSchedule).where(PostSchedule.id == schedule_id)
            )
            schedule = result.scalar_one_or_none()
            if schedule:
                schedule.published = True
                schedule.post_id = post_id
                await session.commit()

    async def get_today_published_count(self) -> int:
        """
        Получение количества опубликованных постов за сегодня

        Returns:
            Количество постов
        """
        async with self.get_session() as session:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            result = await session.execute(
                select(PublishedPost).where(PublishedPost.published_at >= today_start)
            )
            posts = result.scalars().all()
            return len(posts)

    async def close(self):
        """Закрытие соединений с БД"""
        await self.async_engine.dispose()
        logger.info("Соединение с БД закрыто")


# Глобальный объект менеджера БД
db_manager: Optional[DatabaseManager] = None


def init_database(database_url: str = None) -> DatabaseManager:
    """
    Инициализация глобального менеджера БД

    Args:
        database_url: URL подключения к PostgreSQL

    Returns:
        DatabaseManager
    """
    global db_manager
    if database_url is None:
        database_url = bot.config.config.DATABASE_URL
    db_manager = DatabaseManager(database_url)
    return db_manager
