"""
Извлечение полного текста новостей из HTML (ТОЛЬКО html.parser, БЕЗ lxml!)
"""
import aiohttp
from bs4 import BeautifulSoup
from typing import Optional
from bot.core.logger import get_logger

logger = get_logger(__name__)


class NewsExtractor:
    """
    Извлечение полного текста новостей
    """

    def __init__(self):
        """Инициализация экстрактора"""
        logger.info("🔧 NewsExtractor инициализирован")

    async def extract_full_text(self, url: str) -> Optional[str]:
        """
        Извлечь полный текст новости по URL

        Args:
            url: URL новости

        Returns:
            Полный текст новости или None при ошибке
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={'User-Agent': 'Mozilla/5.0'}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"⚠️ Не удалось загрузить {url}: HTTP {response.status}")
                        return None

                    html = await response.text()

                    # Используем ТОЛЬКО html.parser (БЕЗ lxml!)
                    soup = BeautifulSoup(html, 'html.parser')

                    # Извлекаем текст из параграфов
                    paragraphs = soup.find_all('p')
                    text = ' '.join([p.get_text().strip() for p in paragraphs])

                    # Убираем лишние пробелы
                    text = ' '.join(text.split())

                    if len(text) < 100:
                        logger.warning(f"⚠️ Текст слишком короткий для {url}")
                        return None

                    return text

        except Exception as e:
            logger.warning(f"⚠️ Ошибка при извлечении текста из {url}: {e}")
            return None

    async def extract_with_fallback(self, url: str, description: str) -> str:
        """
        Извлечь текст с fallback на описание

        Args:
            url: URL новости
            description: Описание из RSS/API

        Returns:
            Полный текст или описание
        """
        full_text = await self.extract_full_text(url)

        if full_text and len(full_text) > len(description):
            return full_text
        else:
            return description
