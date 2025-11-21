"""
Сбор новостей из различных источников
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import feedparser
import aiohttp
from newsapi import NewsApiClient
from bot.core.logger import get_logger
from bot.core.exceptions import NewsCollectionError
from bot.news.sources import RSS_FEEDS, NEWSAPI_SOURCES, KEYWORDS

logger = get_logger(__name__)


class NewsCollector:
    """
    Сборщик новостей из различных источников
    """

    def __init__(self, newsapi_key: str, max_age_hours: int = 6):
        """
        Инициализация сборщика новостей

        Args:
            newsapi_key: API ключ NewsAPI
            max_age_hours: Максимальный возраст новостей в часах
        """
        self.newsapi_key = newsapi_key
        self.newsapi_client = NewsApiClient(api_key=newsapi_key)
        self.max_age_hours = max_age_hours
        logger.info(f"🔧 NewsCollector инициализирован (max_age: {max_age_hours}ч)")

    async def collect_all_news(self) -> List[Dict[str, Any]]:
        """
        Собрать новости из всех источников

        Returns:
            Список новостей
        """
        logger.info("📰 Начинаю сбор новостей из всех источников...")

        all_news = []

        # Собираем из RSS
        rss_news = await self._collect_from_rss()
        all_news.extend(rss_news)
        logger.info(f"  • RSS: собрано {len(rss_news)} новостей")

        # Собираем из NewsAPI
        newsapi_news = await self._collect_from_newsapi()
        all_news.extend(newsapi_news)
        logger.info(f"  • NewsAPI: собрано {len(newsapi_news)} новостей")

        # Удаляем дубликаты по URL
        unique_news = self._remove_duplicates(all_news)

        # Фильтруем по времени
        recent_news = self._filter_by_time(unique_news)

        logger.info(f"✅ Всего собрано уникальных свежих новостей: {len(recent_news)}")
        return recent_news

    async def _collect_from_rss(self) -> List[Dict[str, Any]]:
        """
        Собрать новости из RSS каналов

        Returns:
            Список новостей
        """
        news = []

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_rss_feed(session, source, url)
                for source, url in RSS_FEEDS.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    news.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"⚠️ Ошибка при сборе RSS: {result}")

        return news

    async def _fetch_rss_feed(
        self,
        session: aiohttp.ClientSession,
        source: str,
        url: str
    ) -> List[Dict[str, Any]]:
        """
        Получить новости из одного RSS канала

        Args:
            session: HTTP сессия
            source: Название источника
            url: URL RSS канала

        Returns:
            Список новостей
        """
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.warning(f"⚠️ {source}: HTTP {response.status}")
                    return []

                content = await response.text()
                feed = feedparser.parse(content)

                news = []
                for entry in feed.entries[:20]:  # Берем только первые 20
                    news_item = {
                        'title': entry.get('title', ''),
                        'url': entry.get('link', ''),
                        'description': entry.get('summary', ''),
                        'published_at': self._parse_date(entry.get('published')),
                        'source': source
                    }
                    news.append(news_item)

                return news

        except Exception as e:
            logger.warning(f"⚠️ Ошибка при получении RSS {source}: {e}")
            return []

    async def _collect_from_newsapi(self) -> List[Dict[str, Any]]:
        """
        Собрать новости из NewsAPI

        Returns:
            Список новостей
        """
        news = []

        try:
            # Получаем новости за последние часы
            from_date = datetime.now(timezone.utc) - timedelta(hours=self.max_age_hours)

            # Ищем по ключевым словам для российских новостей
            query = ' OR '.join(KEYWORDS[:5])  # Используем топ-5 ключевых слов

            # Форматируем дату в ISO 8601 формат (YYYY-MM-DDTHH:MM:SS)
            from_param = from_date.strftime('%Y-%m-%dT%H:%M:%S')

            response = self.newsapi_client.get_everything(
                q=query,
                language='ru',
                from_param=from_param,
                sort_by='publishedAt',
                page_size=50
            )

            if response['status'] == 'ok':
                for article in response['articles']:
                    news_item = {
                        'title': article.get('title', ''),
                        'url': article.get('url', ''),
                        'description': article.get('description', ''),
                        'published_at': self._parse_date(article.get('publishedAt')),
                        'source': article.get('source', {}).get('name', 'NewsAPI')
                    }
                    news.append(news_item)

        except Exception as e:
            logger.warning(f"⚠️ Ошибка при получении новостей из NewsAPI: {e}")

        return news

    def _parse_date(self, date_str: Optional[str]) -> datetime:
        """
        Распарсить дату из строки

        Args:
            date_str: Строка с датой

        Returns:
            datetime объект (timezone-aware UTC)
        """
        if not date_str:
            return datetime.now(timezone.utc)

        try:
            from dateutil import parser
            parsed = parser.parse(date_str)
            # Если дата без timezone, добавляем UTC
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return datetime.now(timezone.utc)

    def _remove_duplicates(self, news: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Удалить дубликаты по URL

        Args:
            news: Список новостей

        Returns:
            Список уникальных новостей
        """
        seen_urls = set()
        unique_news = []

        for item in news:
            url = item.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_news.append(item)

        return unique_news

    def _filter_by_time(self, news: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Отфильтровать новости по времени публикации

        Args:
            news: Список новостей

        Returns:
            Список свежих новостей
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.max_age_hours)
        recent_news = []

        for item in news:
            published_at = item.get('published_at')
            if published_at:
                # Убеждаемся что дата имеет timezone
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)

                if published_at > cutoff_time:
                    recent_news.append(item)

        return recent_news
