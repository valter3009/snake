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

    async def extract_image_url(self, url: str) -> Optional[str]:
        """
        Извлечь URL главного изображения из новости

        Args:
            url: URL новости

        Returns:
            URL изображения или None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={'User-Agent': 'Mozilla/5.0'}
                ) as response:
                    if response.status != 200:
                        return None

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Ищем изображение в разных местах
                    # 1. Open Graph image
                    og_image = soup.find('meta', property='og:image')
                    if og_image and og_image.get('content'):
                        return og_image['content']

                    # 2. Twitter card image
                    twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
                    if twitter_image and twitter_image.get('content'):
                        return twitter_image['content']

                    # 3. Первое большое изображение в статье
                    images = soup.find_all('img')
                    for img in images:
                        src = img.get('src') or img.get('data-src')
                        if src and ('http' in src or src.startswith('//')):
                            # Проверяем размер изображения (если указан)
                            width = img.get('width')
                            height = img.get('height')

                            if width and height:
                                try:
                                    if int(width) >= 400 and int(height) >= 300:
                                        return src if src.startswith('http') else f"https:{src}"
                                except:
                                    pass
                            else:
                                # Если размер не указан, берем первое
                                return src if src.startswith('http') else f"https:{src}"

                    return None

        except Exception as e:
            logger.warning(f"⚠️ Ошибка при извлечении изображения из {url}: {e}")
            return None

    async def extract_video_url(self, url: str) -> Optional[str]:
        """
        Извлечь URL видео из новости

        Args:
            url: URL новости

        Returns:
            URL видео или None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={'User-Agent': 'Mozilla/5.0'}
                ) as response:
                    if response.status != 200:
                        return None

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Ищем видео в разных местах
                    # 1. Open Graph video
                    og_video = soup.find('meta', property='og:video')
                    if og_video and og_video.get('content'):
                        video_url = og_video['content']
                        # Проверяем, что это прямая ссылка на видео
                        if any(ext in video_url.lower() for ext in ['.mp4', '.webm', '.mov']):
                            return video_url

                    # 2. og:video:secure_url
                    og_video_secure = soup.find('meta', property='og:video:secure_url')
                    if og_video_secure and og_video_secure.get('content'):
                        video_url = og_video_secure['content']
                        if any(ext in video_url.lower() for ext in ['.mp4', '.webm', '.mov']):
                            return video_url

                    # 3. Twitter player stream
                    twitter_player = soup.find('meta', attrs={'name': 'twitter:player:stream'})
                    if twitter_player and twitter_player.get('content'):
                        video_url = twitter_player['content']
                        if any(ext in video_url.lower() for ext in ['.mp4', '.webm', '.mov']):
                            return video_url

                    # 4. Video tags в HTML
                    video_tags = soup.find_all('video')
                    for video in video_tags:
                        # Ищем source внутри video
                        source = video.find('source')
                        if source and source.get('src'):
                            src = source['src']
                            if src.startswith('http') or src.startswith('//'):
                                return src if src.startswith('http') else f"https:{src}"

                        # Или src прямо у video
                        src = video.get('src')
                        if src:
                            if src.startswith('http') or src.startswith('//'):
                                return src if src.startswith('http') else f"https:{src}"

                    return None

        except Exception as e:
            logger.warning(f"⚠️ Ошибка при извлечении видео из {url}: {e}")
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
