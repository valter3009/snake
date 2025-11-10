"""
Модуль для парсинга новостей из RSS-фидов и извлечения медиа контента
"""

import feedparser
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import logging
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin, urlparse
import time

from config import (
    NEWS_SOURCES,
    MIN_IMAGE_WIDTH,
    MIN_IMAGE_HEIGHT,
    ALLOWED_IMAGE_FORMATS,
    REQUEST_TIMEOUT,
    MAX_RETRIES
)

logger = logging.getLogger(__name__)


class NewsParser:
    """Класс для парсинга новостей и извлечения медиа"""

    def __init__(self):
        """Инициализация парсера"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_news_from_source(self, source: Dict) -> List[Dict]:
        """
        Получение новостей из одного источника

        Args:
            source: Словарь с информацией об источнике

        Returns:
            Список новостей
        """
        news_list = []

        try:
            logger.info(f"Парсинг источника: {source['name']}")

            # Парсинг RSS фида
            feed = feedparser.parse(source['url'])

            if feed.bozo:
                logger.warning(f"Проблема с фидом {source['name']}: {feed.bozo_exception}")

            # Обработка каждой новости
            for entry in feed.entries[:10]:  # Берем последние 10 новостей
                try:
                    news_item = {
                        'title': entry.get('title', '').strip(),
                        'description': entry.get('summary', entry.get('description', '')).strip(),
                        'url': entry.get('link', ''),
                        'source': source['name'],
                        'category': source['category'],
                        'published': entry.get('published', ''),
                    }

                    # Очистка HTML тегов из описания
                    if news_item['description']:
                        soup = BeautifulSoup(news_item['description'], 'html.parser')
                        news_item['description'] = soup.get_text().strip()

                    news_list.append(news_item)

                except Exception as e:
                    logger.error(f"Ошибка обработки новости: {e}")
                    continue

            logger.info(f"Получено {len(news_list)} новостей из {source['name']}")

        except Exception as e:
            logger.error(f"Ошибка парсинга источника {source['name']}: {e}")

        return news_list

    def fetch_all_news(self) -> List[Dict]:
        """
        Получение новостей из всех источников

        Returns:
            Список всех новостей
        """
        all_news = []

        for source in NEWS_SOURCES:
            try:
                news = self.fetch_news_from_source(source)
                all_news.extend(news)
                time.sleep(1)  # Пауза между запросами к разным источникам
            except Exception as e:
                logger.error(f"Ошибка при получении новостей: {e}")
                continue

        logger.info(f"Всего получено новостей: {len(all_news)}")
        return all_news

    def extract_image_from_page(self, url: str) -> Optional[Tuple[bytes, str]]:
        """
        Извлечение изображения со страницы новости

        Args:
            url: URL страницы новости

        Returns:
            Кортеж (байты изображения, формат) или None
        """
        if not url:
            return None

        for attempt in range(MAX_RETRIES):
            try:
                # Загрузка страницы
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'html.parser')

                # Поиск изображения в различных местах
                image_url = self._find_image_url(soup, url)

                if image_url:
                    # Загрузка и проверка изображения
                    image_data = self._download_and_validate_image(image_url)
                    if image_data:
                        return image_data

            except requests.RequestException as e:
                logger.warning(f"Попытка {attempt + 1}/{MAX_RETRIES} не удалась: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # Экспоненциальная задержка
                continue
            except Exception as e:
                logger.error(f"Ошибка извлечения изображения: {e}")
                break

        return None

    def _find_image_url(self, soup: BeautifulSoup, page_url: str) -> Optional[str]:
        """
        Поиск URL изображения на странице

        Args:
            soup: Объект BeautifulSoup
            page_url: URL страницы для формирования абсолютных путей

        Returns:
            URL изображения или None
        """
        # Поиск в Open Graph мета-тегах
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return urljoin(page_url, og_image['content'])

        # Поиск в Twitter Card мета-тегах
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            return urljoin(page_url, twitter_image['content'])

        # Поиск первого большого изображения в статье
        article_images = soup.find_all('img', class_=lambda x: x and ('article' in x or 'content' in x or 'main' in x))
        for img in article_images:
            img_url = img.get('src') or img.get('data-src')
            if img_url:
                return urljoin(page_url, img_url)

        # Поиск по общим селекторам
        main_content = soup.find(['article', 'main', 'div'], class_=lambda x: x and ('content' in x or 'article' in x))
        if main_content:
            img = main_content.find('img')
            if img:
                img_url = img.get('src') or img.get('data-src')
                if img_url:
                    return urljoin(page_url, img_url)

        # Поиск любого подходящего изображения
        images = soup.find_all('img')
        for img in images:
            img_url = img.get('src') or img.get('data-src')
            if img_url and not self._is_icon_or_logo(img_url):
                return urljoin(page_url, img_url)

        return None

    @staticmethod
    def _is_icon_or_logo(url: str) -> bool:
        """
        Проверка, является ли изображение иконкой или логотипом

        Args:
            url: URL изображения

        Returns:
            True если это иконка/логотип
        """
        url_lower = url.lower()
        exclude_keywords = ['logo', 'icon', 'favicon', 'avatar', 'sprite', 'button']
        return any(keyword in url_lower for keyword in exclude_keywords)

    def _download_and_validate_image(self, image_url: str) -> Optional[Tuple[bytes, str]]:
        """
        Загрузка и валидация изображения

        Args:
            image_url: URL изображения

        Returns:
            Кортеж (байты изображения, формат) или None
        """
        try:
            # Загрузка изображения
            response = self.session.get(image_url, timeout=REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()

            # Проверка размера (не более 10 МБ)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 10 * 1024 * 1024:
                logger.warning(f"Изображение слишком большое: {content_length} bytes")
                return None

            # Загрузка содержимого
            image_bytes = response.content

            # Проверка и валидация изображения
            try:
                img = Image.open(BytesIO(image_bytes))

                # Проверка формата
                if img.format not in ALLOWED_IMAGE_FORMATS:
                    logger.warning(f"Неподдерживаемый формат: {img.format}")
                    return None

                # Проверка размеров
                width, height = img.size
                if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                    logger.warning(f"Изображение слишком маленькое: {width}x{height}")
                    return None

                # Конвертация WebP в JPEG если нужно
                if img.format == 'WebP':
                    output = BytesIO()
                    img.convert('RGB').save(output, format='JPEG', quality=85)
                    image_bytes = output.getvalue()
                    img_format = 'JPEG'
                else:
                    img_format = img.format

                logger.info(f"Изображение валидно: {width}x{height}, {img_format}")
                return (image_bytes, img_format)

            except Exception as e:
                logger.error(f"Ошибка обработки изображения: {e}")
                return None

        except requests.RequestException as e:
            logger.warning(f"Ошибка загрузки изображения: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке изображения: {e}")
            return None

    def get_news_with_media(self, news_item: Dict) -> Dict:
        """
        Получение новости с медиа контентом

        Args:
            news_item: Словарь с данными новости

        Returns:
            Обновленный словарь новости с медиа
        """
        # Попытка извлечь изображение
        media_data = self.extract_image_from_page(news_item['url'])

        if media_data:
            news_item['media_data'] = media_data[0]
            news_item['media_format'] = media_data[1]
            logger.info(f"Медиа добавлено к новости: {news_item['title'][:50]}...")
        else:
            news_item['media_data'] = None
            news_item['media_format'] = None
            logger.info(f"Медиа не найдено для новости: {news_item['title'][:50]}...")

        return news_item
