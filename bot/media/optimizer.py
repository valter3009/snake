"""
Оптимизация изображений для публикации
"""
import io
from typing import Optional, Tuple
from PIL import Image
from bot.core.logger import get_logger
from bot.core.exceptions import MediaError

logger = get_logger(__name__)


class ImageOptimizer:
    """
    Оптимизация изображений для Telegram
    """

    def __init__(self, max_size: Tuple[int, int] = (1280, 720), quality: int = 85):
        """
        Инициализация оптимизатора

        Args:
            max_size: Максимальный размер (ширина, высота)
            quality: Качество JPEG (0-100)
        """
        self.max_size = max_size
        self.quality = quality
        logger.info(f"🔧 ImageOptimizer инициализирован (max_size: {max_size}, quality: {quality})")

    def optimize_image(self, image_bytes: bytes) -> Optional[bytes]:
        """
        Оптимизировать изображение

        Args:
            image_bytes: Исходные байты изображения

        Returns:
            Оптимизированные байты или None при ошибке
        """
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(image_bytes))

            # Конвертируем в RGB если нужно
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background

            # Изменяем размер если больше максимального
            if image.size[0] > self.max_size[0] or image.size[1] > self.max_size[1]:
                image.thumbnail(self.max_size, Image.Resampling.LANCZOS)
                logger.info(f"📏 Размер изменен на: {image.size}")

            # Сохраняем в буфер
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=self.quality, optimize=True)
            optimized_bytes = output.getvalue()

            original_size = len(image_bytes)
            optimized_size = len(optimized_bytes)
            reduction = ((original_size - optimized_size) / original_size) * 100

            logger.info(f"✅ Изображение оптимизировано: {original_size//1024}KB → {optimized_size//1024}KB (-{reduction:.1f}%)")

            return optimized_bytes

        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации изображения: {e}")
            return None

    def validate_image(self, image_bytes: bytes) -> bool:
        """
        Проверить валидность изображения

        Args:
            image_bytes: Байты изображения

        Returns:
            True если изображение валидно
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image.verify()
            return True
        except Exception as e:
            logger.warning(f"⚠️ Невалидное изображение: {e}")
            return False

    def get_image_info(self, image_bytes: bytes) -> Optional[dict]:
        """
        Получить информацию об изображении

        Args:
            image_bytes: Байты изображения

        Returns:
            Словарь с информацией
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))

            info = {
                'format': image.format,
                'mode': image.mode,
                'size': image.size,
                'width': image.size[0],
                'height': image.size[1],
                'file_size': len(image_bytes)
            }

            return info

        except Exception as e:
            logger.error(f"❌ Ошибка получения информации об изображении: {e}")
            return None
