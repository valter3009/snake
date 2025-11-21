"""
Обработка медиа файлов для новостей
"""
import aiohttp
from typing import Optional, Dict, Any
from bot.core.logger import get_logger
from bot.core.exceptions import MediaError
from bot.media.optimizer import ImageOptimizer

logger = get_logger(__name__)


class MediaHandler:
    """
    Обработка медиа контента для новостей
    """

    def __init__(self):
        """Инициализация обработчика медиа"""
        self.optimizer = ImageOptimizer()
        logger.info("🔧 MediaHandler инициализирован")

    async def download_image(self, url: str) -> Optional[bytes]:
        """
        Скачать изображение по URL

        Args:
            url: URL изображения

        Returns:
            Байты изображения или None при ошибке
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={'User-Agent': 'Mozilla/5.0'}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"⚠️ Не удалось скачать изображение: HTTP {response.status}")
                        return None

                    image_bytes = await response.read()

                    # Проверяем размер (не более 10MB)
                    if len(image_bytes) > 10 * 1024 * 1024:
                        logger.warning("⚠️ Изображение слишком большое (>10MB)")
                        return None

                    logger.info(f"📥 Изображение скачано ({len(image_bytes)//1024}KB)")
                    return image_bytes

        except Exception as e:
            logger.warning(f"⚠️ Ошибка скачивания изображения: {e}")
            return None

    async def extract_image_from_news(self, news_item: Dict[str, Any]) -> Optional[str]:
        """
        Извлечь URL изображения из новости

        Args:
            news_item: Данные новости

        Returns:
            URL изображения или None
        """
        # Пытаемся найти изображение в разных полях
        possible_fields = ['urlToImage', 'image', 'thumbnail', 'media']

        for field in possible_fields:
            if field in news_item and news_item[field]:
                image_url = news_item[field]
                if isinstance(image_url, str) and image_url.startswith('http'):
                    return image_url

        return None

    async def process_news_media(self, news_item: Dict[str, Any]) -> Optional[bytes]:
        """
        Обработать медиа для новости (скачать и оптимизировать)

        Args:
            news_item: Данные новости

        Returns:
            Оптимизированные байты изображения или None
        """
        try:
            # Извлекаем URL изображения
            image_url = await self.extract_image_from_news(news_item)

            if not image_url:
                logger.info("📷 Изображение не найдено в новости")
                return None

            # Скачиваем изображение
            image_bytes = await self.download_image(image_url)

            if not image_bytes:
                return None

            # Проверяем валидность
            if not self.optimizer.validate_image(image_bytes):
                logger.warning("⚠️ Изображение не прошло валидацию")
                return None

            # Оптимизируем
            optimized_bytes = self.optimizer.optimize_image(image_bytes)

            if optimized_bytes:
                logger.info("✅ Медиа обработано успешно")

            return optimized_bytes

        except Exception as e:
            logger.error(f"❌ Ошибка обработки медиа: {e}")
            return None

    async def get_media_url_for_telegram(self, news_item: Dict[str, Any]) -> Optional[str]:
        """
        Получить URL медиа для отправки в Telegram (без скачивания)

        Args:
            news_item: Данные новости

        Returns:
            URL изображения или None
        """
        image_url = await self.extract_image_from_news(news_item)

        if image_url:
            # Проверяем, что URL доступен
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.head(image_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status == 200:
                            return image_url
            except Exception as e:
                logger.warning(f"⚠️ URL изображения недоступен: {e}")

        return None
