"""
Модуль для работы с базой данных SQLite
Хранит информацию об опубликованных новостях для избежания дубликатов
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict
import hashlib

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


class NewsDatabase:
    """Класс для работы с базой данных новостей"""

    def __init__(self, db_path: str = DATABASE_PATH):
        """
        Инициализация базы данных

        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Создание таблиц в базе данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Таблица опубликованных новостей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS published_news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_hash TEXT UNIQUE NOT NULL,
                    original_url TEXT,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    telegram_message_id INTEGER,
                    has_media BOOLEAN DEFAULT 0
                )
            ''')

            # Таблица статистики
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    posts_published INTEGER DEFAULT 0,
                    posts_failed INTEGER DEFAULT 0,
                    UNIQUE(date)
                )
            ''')

            # Индексы для быстрого поиска
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_news_hash
                ON published_news(news_hash)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_published_at
                ON published_news(published_at)
            ''')

            conn.commit()
            conn.close()
            logger.info("База данных успешно инициализирована")

        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise

    @staticmethod
    def generate_news_hash(title: str, url: Optional[str] = None) -> str:
        """
        Генерация уникального хеша для новости

        Args:
            title: Заголовок новости
            url: URL новости (опционально)

        Returns:
            Хеш строка
        """
        content = f"{title}:{url or ''}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def is_news_published(self, title: str, url: Optional[str] = None) -> bool:
        """
        Проверка, была ли новость уже опубликована

        Args:
            title: Заголовок новости
            url: URL новости (опционально)

        Returns:
            True если новость уже опубликована, иначе False
        """
        news_hash = self.generate_news_hash(title, url)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                'SELECT COUNT(*) FROM published_news WHERE news_hash = ?',
                (news_hash,)
            )

            count = cursor.fetchone()[0]
            conn.close()

            return count > 0

        except Exception as e:
            logger.error(f"Ошибка проверки новости в БД: {e}")
            return False

    def add_published_news(
        self,
        title: str,
        source: str,
        url: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        has_media: bool = False
    ) -> bool:
        """
        Добавление опубликованной новости в базу

        Args:
            title: Заголовок новости
            source: Источник новости
            url: URL новости (опционально)
            telegram_message_id: ID сообщения в Telegram
            has_media: Наличие медиа файлов

        Returns:
            True если успешно добавлено, иначе False
        """
        news_hash = self.generate_news_hash(title, url)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO published_news
                (news_hash, original_url, title, source, telegram_message_id, has_media)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (news_hash, url, title, source, telegram_message_id, has_media))

            conn.commit()
            conn.close()

            logger.info(f"Новость добавлена в БД: {title[:50]}...")
            return True

        except sqlite3.IntegrityError:
            logger.warning(f"Новость уже существует в БД: {title[:50]}...")
            return False
        except Exception as e:
            logger.error(f"Ошибка добавления новости в БД: {e}")
            return False

    def get_published_count_today(self) -> int:
        """
        Получение количества опубликованных новостей за сегодня

        Returns:
            Количество опубликованных новостей
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().date()
            cursor.execute('''
                SELECT COUNT(*) FROM published_news
                WHERE DATE(published_at) = ?
            ''', (today,))

            count = cursor.fetchone()[0]
            conn.close()

            return count

        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return 0

    def get_recent_news(self, limit: int = 10) -> List[Dict]:
        """
        Получение последних опубликованных новостей

        Args:
            limit: Количество новостей для получения

        Returns:
            Список словарей с информацией о новостях
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM published_news
                ORDER BY published_at DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Ошибка получения последних новостей: {e}")
            return []

    def update_statistics(self, success: bool = True):
        """
        Обновление статистики публикаций

        Args:
            success: True если публикация успешна, False если ошибка
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().date()
            field = 'posts_published' if success else 'posts_failed'

            cursor.execute(f'''
                INSERT INTO statistics (date, {field})
                VALUES (?, 1)
                ON CONFLICT(date) DO UPDATE SET
                {field} = {field} + 1
            ''', (today,))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Ошибка обновления статистики: {e}")

    def get_statistics(self, days: int = 7) -> List[Dict]:
        """
        Получение статистики за последние дни

        Args:
            days: Количество дней для статистики

        Returns:
            Список словарей со статистикой
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM statistics
                ORDER BY date DESC
                LIMIT ?
            ''', (days,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return []

    def cleanup_old_records(self, days: int = 30):
        """
        Очистка старых записей из базы данных

        Args:
            days: Количество дней, после которых записи удаляются
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM published_news
                WHERE published_at < datetime('now', '-' || ? || ' days')
            ''', (days,))

            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"Удалено старых записей: {deleted}")

        except Exception as e:
            logger.error(f"Ошибка очистки базы данных: {e}")
