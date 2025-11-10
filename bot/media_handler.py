"""
Обработка медиафайлов (фото/видео) для Telegram
"""
import logging
import os
import tempfile
from typing import Optional
from io import BytesIO

import aiohttp
from PIL import Image

logger = logging.getLogger(__name__)


class MediaHandler:
    """Обработчик медиафайлов"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        # Максимальный размер изображения в пикселях
        self.max_image_size = (1280, 1280)
        # Максимальный размер файла (в байтах) - 10 MB
        self.max_file_size = 10 * 1024 * 1024

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание aiohttp сессии"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def download_and_optimize_image(self, image_url: str) -> Optional[BytesIO]:
        """
        Скачивание и оптимизация изображения

        Args:
            image_url: URL изображения

        Returns:
            BytesIO с оптимизированным изображением или None при ошибке
        """
        if not image_url:
            return None

        try:
            logger.info(f"Скачиваем изображение: {image_url}")
            session = await self._get_session()

            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    logger.warning(f"Не удалось скачать изображение, статус: {response.status}")
                    return None

                # Проверяем размер файла
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > self.max_file_size:
                    logger.warning(f"Файл слишком большой: {content_length} байт")
                    return None

                # Скачиваем изображение
                image_data = await response.read()

                # Оптимизируем изображение
                optimized = await self._optimize_image(image_data)

                logger.info(f"Изображение успешно обработано")
                return optimized

        except Exception as e:
            logger.error(f"Ошибка при скачивании/оптимизации изображения: {e}")
            return None

    async def _optimize_image(self, image_data: bytes) -> Optional[BytesIO]:
        """
        Оптимизация изображения (изменение размера, сжатие)

        Args:
            image_data: Данные изображения

        Returns:
            BytesIO с оптимизированным изображением
        """
        try:
            # Открываем изображение
            image = Image.open(BytesIO(image_data))

            # Конвертируем в RGB если необходимо
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background

            # Изменяем размер если изображение слишком большое
            if image.size[0] > self.max_image_size[0] or image.size[1] > self.max_image_size[1]:
                image.thumbnail(self.max_image_size, Image.Resampling.LANCZOS)
                logger.info(f"Размер изображения уменьшен до {image.size}")

            # Сохраняем оптимизированное изображение
            output = BytesIO()
            image.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)

            return output

        except Exception as e:
            logger.error(f"Ошибка оптимизации изображения: {e}")
            return None

    async def validate_image_url(self, image_url: str) -> bool:
        """
        Проверка доступности изображения по URL

        Args:
            image_url: URL изображения

        Returns:
            True если изображение доступно
        """
        if not image_url:
            return False

        try:
            session = await self._get_session()
            async with session.head(image_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '')
                    return content_type.startswith('image/')
                return False

        except Exception as e:
            logger.warning(f"Ошибка проверки URL изображения: {e}")
            return False


# Глобальный объект обработчика медиа
media_handler: Optional[MediaHandler] = None


def init_media_handler() -> MediaHandler:
    """
    Инициализация глобального обработчика медиа

    Returns:
        MediaHandler
    """
    global media_handler
    media_handler = MediaHandler()
    return media_handler
