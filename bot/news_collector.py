"""
Сбор новостей из NewsAPI и RSS лент
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncio

import aiohttp
import feedparser
from dateutil import parser as date_parser

import bot.config
from bot.database import db_manager

logger = logging.getLogger(__name__)


class NewsArticle:
    """Класс для представления новости"""

    def __init__(
        self,
        title: str,
        url: str,
        source: str,
        published_at: datetime,
        description: Optional[str] = None,
        content: Optional[str] = None,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        author: Optional[str] = None
    ):
        self.title = title
        self.url = url
        self.source = source
        self.published_at = published_at
        self.description = description or ""
        self.content = content or ""
        self.image_url = image_url
        self.video_url = video_url
        self.author = author

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь"""
        return {
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'published_at': self.published_at.isoformat(),
            'description': self.description,
            'content': self.content,
            'image_url': self.image_url,
            'video_url': self.video_url,
            'author': self.author
        }

    def __repr__(self):
        return f"<NewsArticle(title='{self.title[:50]}...', source='{self.source}')>"


class NewsCollector:
    """Коллектор новостей из различных источников"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание aiohttp сессии"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def collect_news(self) -> List[NewsArticle]:
        """
        Сбор новостей из всех источников

        Returns:
            Список объектов NewsArticle
        """
        logger.info("Начинаем сбор новостей...")

        # Собираем новости параллельно
        tasks = [
            self.collect_from_newsapi(),
            self.collect_from_rss_feeds()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_news = []
        for result in results:
            if isinstance(result, list):
                all_news.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Ошибка при сборе новостей: {result}")

        # Фильтруем свежие новости
        fresh_news = await self._filter_fresh_news(all_news)

        # Удаляем дубликаты
        unique_news = await self._remove_duplicates(fresh_news)

        logger.info(f"Собрано {len(unique_news)} уникальных новостей")
        return unique_news

    async def collect_from_newsapi(self) -> List[NewsArticle]:
        """
        Сбор новостей из NewsAPI

        Returns:
            Список новостей
        """
        news_list = []

        try:
            session = await self._get_session()

            for language in bot.config.config.NEWS_API_LANGUAGES:
                for category in bot.config.config.NEWS_API_CATEGORIES:
                    url = "https://newsapi.org/v2/top-headlines"
                    params = {
                        'apiKey': bot.config.config.NEWS_API_KEY,
                        'language': language,
                        'category': category,
                        'pageSize': 20
                    }

                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            articles = data.get('articles', [])

                            for article in articles:
                                try:
                                    # Парсим дату публикации
                                    published_at = date_parser.parse(article['publishedAt'])

                                    news = NewsArticle(
                                        title=article['title'],
                                        url=article['url'],
                                        source=article['source']['name'],
                                        published_at=published_at,
                                        description=article.get('description'),
                                        content=article.get('content'),
                                        image_url=article.get('urlToImage'),
                                        author=article.get('author')
                                    )
                                    news_list.append(news)
                                except Exception as e:
                                    logger.warning(f"Ошибка парсинга статьи из NewsAPI: {e}")
                                    continue

                        else:
                            logger.warning(f"NewsAPI вернул статус {response.status}")

                    # Небольшая задержка между запросами
                    await asyncio.sleep(0.5)

            logger.info(f"Собрано {len(news_list)} новостей из NewsAPI")

        except Exception as e:
            logger.error(f"Ошибка сбора из NewsAPI: {e}")

        return news_list

    async def collect_from_rss_feeds(self) -> List[NewsArticle]:
        """
        Сбор новостей из RSS лент

        Returns:
            Список новостей
        """
        news_list = []

        try:
            session = await self._get_session()

            for feed_url in bot.config.config.RSS_FEEDS:
                try:
                    # Определяем источник по URL
                    source = self._get_source_name(feed_url)

                    async with session.get(feed_url) as response:
                        if response.status == 200:
                            content = await response.text()
                            feed = feedparser.parse(content)

                            for entry in feed.entries:
                                try:
                                    # Парсим дату публикации
                                    if hasattr(entry, 'published'):
                                        published_at = date_parser.parse(entry.published)
                                    elif hasattr(entry, 'updated'):
                                        published_at = date_parser.parse(entry.updated)
                                    else:
                                        published_at = datetime.utcnow()

                                    # Получаем изображение и видео
                                    image_url = None
                                    video_url = None

                                    if hasattr(entry, 'media_content') and entry.media_content:
                                        for media in entry.media_content:
                                            media_type = media.get('type', '')
                                            if media_type.startswith('video/') and not video_url:
                                                video_url = media.get('url')
                                            elif media_type.startswith('image/') and not image_url:
                                                image_url = media.get('url')

                                    if hasattr(entry, 'enclosures') and entry.enclosures:
                                        for enclosure in entry.enclosures:
                                            enc_type = enclosure.get('type', '')
                                            enc_url = enclosure.get('href', '')
                                            if enc_type.startswith('video/') and not video_url:
                                                video_url = enc_url
                                            elif enc_type.startswith('image/') and not image_url:
                                                image_url = enc_url

                                    news = NewsArticle(
                                        title=entry.title,
                                        url=entry.link,
                                        source=source,
                                        published_at=published_at,
                                        description=entry.get('summary', ''),
                                        content=entry.get('content', [{}])[0].get('value', ''),
                                        image_url=image_url,
                                        video_url=video_url,
                                        author=entry.get('author')
                                    )
                                    news_list.append(news)

                                except Exception as e:
                                    logger.warning(f"Ошибка парсинга записи из RSS {feed_url}: {e}")
                                    continue

                        else:
                            logger.warning(f"RSS лента {feed_url} вернула статус {response.status}")

                except Exception as e:
                    logger.error(f"Ошибка сбора из RSS {feed_url}: {e}")
                    continue

            logger.info(f"Собрано {len(news_list)} новостей из RSS лент")

        except Exception as e:
            logger.error(f"Ошибка сбора из RSS: {e}")

        return news_list

    def _get_source_name(self, feed_url: str) -> str:
        """
        Определение названия источника по URL

        Args:
            feed_url: URL RSS ленты

        Returns:
            Название источника
        """
        if 'rbc.ru' in feed_url:
            return 'RBC'
        elif 'tass.ru' in feed_url:
            return 'TASS'
        elif 'kommersant.ru' in feed_url:
            return 'Коммерсантъ'
        else:
            return 'RSS'

    async def _filter_fresh_news(self, news_list: List[NewsArticle]) -> List[NewsArticle]:
        """
        Фильтрация свежих новостей (не старше NEWS_MAX_AGE_HOURS)

        Args:
            news_list: Список новостей

        Returns:
            Отфильтрованный список
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=bot.config.config.NEWS_MAX_AGE_HOURS)
        fresh_news = [
            news for news in news_list
            if news.published_at >= cutoff_time
        ]
        logger.info(f"Отфильтровано {len(fresh_news)} свежих новостей из {len(news_list)}")
        return fresh_news

    async def _remove_duplicates(self, news_list: List[NewsArticle]) -> List[NewsArticle]:
        """
        Удаление дубликатов и проверка на уже опубликованные

        Args:
            news_list: Список новостей

        Returns:
            Список без дубликатов
        """
        unique_news = []
        seen_urls = set()

        for news in news_list:
            # Проверяем, не видели ли мы этот URL
            if news.url in seen_urls:
                continue

            # Проверяем, не опубликован ли уже
            if db_manager:
                is_published = await db_manager.is_post_published(news.url)
                if is_published:
                    continue

            unique_news.append(news)
            seen_urls.add(news.url)

        logger.info(f"Удалено {len(news_list) - len(unique_news)} дубликатов")
        return unique_news


# Глобальный объект коллектора
news_collector: Optional[NewsCollector] = None


def init_news_collector() -> NewsCollector:
    """
    Инициализация глобального коллектора новостей

    Returns:
        NewsCollector
    """
    global news_collector
    news_collector = NewsCollector()
    return news_collector
