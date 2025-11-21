"""
Извлечение полного текста статей из веб-страниц
"""
import logging
from typing import Optional
import re

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ArticleExtractor:
    """Экстрактор полного текста статей"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        # Максимальный размер HTML для загрузки (5 MB)
        self.max_html_size = 5 * 1024 * 1024

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание aiohttp сессии"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def extract_article_text(self, url: str) -> Optional[str]:
        """
        Извлечение полного текста статьи из URL

        Args:
            url: URL статьи

        Returns:
            Полный текст статьи или None при ошибке
        """
        if not url:
            return None

        try:
            logger.info(f"Извлекаем текст статьи: {url}")
            session = await self._get_session()

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Не удалось загрузить страницу, статус: {response.status}")
                    return None

                # Проверяем размер
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > self.max_html_size:
                    logger.warning(f"HTML слишком большой: {content_length} байт")
                    return None

                html = await response.text()

            # Парсим HTML
            article_text = self._extract_text_from_html(html, url)

            if article_text:
                logger.info(f"Извлечено {len(article_text)} символов текста")
                return article_text

            return None

        except Exception as e:
            logger.error(f"Ошибка извлечения текста статьи: {e}")
            return None

    def _extract_text_from_html(self, html: str, url: str) -> Optional[str]:
        """
        Извлечение текста из HTML

        Args:
            html: HTML код страницы
            url: URL для определения источника

        Returns:
            Извлеченный текст
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Удаляем ненужные теги
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe']):
                tag.decompose()

            # Стратегии извлечения для разных источников
            article_text = None

            # Для РБК
            if 'rbc.ru' in url:
                article_text = self._extract_rbc(soup)
            # Для ТАСС
            elif 'tass.ru' in url:
                article_text = self._extract_tass(soup)
            # Для Коммерсантъ
            elif 'kommersant.ru' in url:
                article_text = self._extract_kommersant(soup)
            # Общая стратегия
            else:
                article_text = self._extract_generic(soup)

            if article_text:
                # Очищаем текст
                article_text = self._clean_text(article_text)
                return article_text

            return None

        except Exception as e:
            logger.error(f"Ошибка парсинга HTML: {e}")
            return None

    def _extract_rbc(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение текста для РБК"""
        # Ищем основной контент
        content = soup.find('div', class_=re.compile(r'article__text'))
        if content:
            paragraphs = content.find_all('p')
            return '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        return None

    def _extract_tass(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение текста для ТАСС"""
        content = soup.find('div', class_=re.compile(r'text-block'))
        if content:
            paragraphs = content.find_all('p')
            return '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        return None

    def _extract_kommersant(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение текста для Коммерсантъ"""
        content = soup.find('div', class_=re.compile(r'article_text'))
        if content:
            paragraphs = content.find_all('p')
            return '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        return None

    def _extract_generic(self, soup: BeautifulSoup) -> Optional[str]:
        """Общая стратегия извлечения текста"""
        # Пробуем найти article tag
        article = soup.find('article')
        if article:
            paragraphs = article.find_all('p')
            if paragraphs:
                return '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

        # Пробуем найти main tag
        main = soup.find('main')
        if main:
            paragraphs = main.find_all('p')
            if paragraphs:
                return '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

        # Последняя попытка - все параграфы
        paragraphs = soup.find_all('p')
        if paragraphs and len(paragraphs) > 3:
            text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            # Проверяем, что получили достаточно текста
            if len(text) > 300:
                return text

        return None

    def _clean_text(self, text: str) -> str:
        """
        Очистка текста

        Args:
            text: Исходный текст

        Returns:
            Очищенный текст
        """
        # Удаляем лишние пробелы и переносы
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        text = text.strip()

        # Ограничиваем длину (максимум 10000 символов)
        if len(text) > 10000:
            text = text[:10000] + '...'

        return text


# Глобальный объект экстрактора
article_extractor: Optional[ArticleExtractor] = None


def init_article_extractor() -> ArticleExtractor:
    """
    Инициализация глобального экстрактора статей

    Returns:
        ArticleExtractor
    """
    global article_extractor
    article_extractor = ArticleExtractor()
    return article_extractor
