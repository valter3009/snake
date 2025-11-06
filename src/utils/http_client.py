"""
HTTP клиент с автоматическими повторами и обработкой ошибок.

Используется для всех запросов к внешним API с умной retry-логикой.
"""

import asyncio
import aiohttp
from typing import Dict, Optional, Any
from utils.logger import get_logger

logger = get_logger(__name__)


class HTTPClient:
    """
    Асинхронный HTTP клиент с автоматическими повторами при ошибках.

    Features:
    - Автоматические retry при сетевых ошибках
    - Exponential backoff (экспоненциальная задержка)
    - Настраиваемые таймауты
    - Логирование всех запросов
    """

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Инициализирует HTTP клиент.

        Args:
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество повторов
            retry_delay: Начальная задержка перед повтором (секунды)
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает или создает сессию aiohttp."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        """Закрывает HTTP сессию."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[Dict]:
        """
        Выполняет GET запрос с автоматическими повторами.

        Args:
            url: URL для запроса
            params: Query параметры
            headers: HTTP заголовки

        Returns:
            Dict или None: JSON ответ или None при ошибке

        Example:
            >>> client = HTTPClient()
            >>> data = await client.get('https://api.coingecko.com/api/v3/ping')
            >>> print(data)
            {'gecko_says': '(V3) To the Moon!'}
        """
        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()

                logger.debug(f"GET {url} (попытка {attempt + 1}/{self.max_retries})")

                async with session.get(url, params=params, headers=headers) as response:
                    # Проверяем статус код
                    if response.status == 429:
                        # Rate limit - ждем дольше
                        delay = self.retry_delay * (2 ** attempt) * 2
                        logger.warning(f"Rate limit для {url}, ожидание {delay}с")
                        await asyncio.sleep(delay)
                        continue

                    if response.status >= 500:
                        # Серверная ошибка - повторяем
                        logger.warning(f"Серверная ошибка {response.status} для {url}")
                        if attempt < self.max_retries - 1:
                            delay = self.retry_delay * (2 ** attempt)
                            await asyncio.sleep(delay)
                            continue

                    # Успешный ответ
                    response.raise_for_status()
                    data = await response.json()

                    logger.debug(f"✅ GET {url} успешно")
                    return data

            except aiohttp.ClientError as e:
                logger.error(f"Сетевая ошибка при GET {url}: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Повтор через {delay}с...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Не удалось выполнить GET {url} после {self.max_retries} попыток")
                    return None

            except Exception as e:
                logger.error(f"Неожиданная ошибка при GET {url}: {e}", exc_info=True)
                return None

        return None

    async def post(
        self,
        url: str,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[Dict]:
        """
        Выполняет POST запрос с автоматическими повторами.

        Args:
            url: URL для запроса
            data: Form data
            json: JSON данные
            headers: HTTP заголовки

        Returns:
            Dict или None: JSON ответ или None при ошибке
        """
        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()

                logger.debug(f"POST {url} (попытка {attempt + 1}/{self.max_retries})")

                async with session.post(url, data=data, json=json, headers=headers) as response:
                    if response.status == 429:
                        delay = self.retry_delay * (2 ** attempt) * 2
                        logger.warning(f"Rate limit для {url}, ожидание {delay}с")
                        await asyncio.sleep(delay)
                        continue

                    if response.status >= 500:
                        logger.warning(f"Серверная ошибка {response.status} для {url}")
                        if attempt < self.max_retries - 1:
                            delay = self.retry_delay * (2 ** attempt)
                            await asyncio.sleep(delay)
                            continue

                    response.raise_for_status()
                    result = await response.json()

                    logger.debug(f"✅ POST {url} успешно")
                    return result

            except aiohttp.ClientError as e:
                logger.error(f"Сетевая ошибка при POST {url}: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Повтор через {delay}с...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Не удалось выполнить POST {url}")
                    return None

            except Exception as e:
                logger.error(f"Неожиданная ошибка при POST {url}: {e}", exc_info=True)
                return None

        return None


# Глобальный экземпляр для использования во всем приложении
http_client = HTTPClient()
