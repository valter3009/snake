"""
Базовый класс для всех коллекторов данных.

Определяет общий интерфейс для сбора данных из различных источников.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from utils.logger import get_logger
from utils.http_client import http_client

logger = get_logger(__name__)


class BaseCollector(ABC):
    """
    Абстрактный базовый класс для всех коллекторов.

    Все collectors должны наследоваться от этого класса и реализовать
    метод collect_data().
    """

    def __init__(self, name: str):
        """
        Инициализирует коллектор.

        Args:
            name: Название коллектора для логирования
        """
        self.name = name
        self.http = http_client
        logger.info(f"Инициализирован коллектор: {name}")

    @abstractmethod
    async def collect_data(self) -> List[Dict]:
        """
        Собирает данные из источника.

        Returns:
            List[Dict]: Список событий/данных

        Note:
            Этот метод должен быть реализован в каждом конкретном коллекторе.
        """
        pass

    async def fetch_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Загружает JSON данные с URL.

        Args:
            url: URL для запроса
            params: Query параметры

        Returns:
            Dict или None: JSON данные или None при ошибке
        """
        logger.debug(f"[{self.name}] Fetching: {url}")
        return await self.http.get(url, params=params)

    def log_success(self, message: str):
        """Логирует успешное выполнение."""
        logger.info(f"[{self.name}] ✅ {message}")

    def log_error(self, message: str, exc: Optional[Exception] = None):
        """Логирует ошибку."""
        if exc:
            logger.error(f"[{self.name}] ❌ {message}: {exc}", exc_info=True)
        else:
            logger.error(f"[{self.name}] ❌ {message}")

    def log_warning(self, message: str):
        """Логирует предупреждение."""
        logger.warning(f"[{self.name}] ⚠️ {message}")
