"""
Базовый класс для торговых стратегий
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Optional


class BaseStrategy(ABC):
    """Абстрактный базовый класс для торговых стратегий"""

    def __init__(self, name: str = "BaseStrategy"):
        """
        Инициализация стратегии

        Args:
            name: Название стратегии
        """
        self.name = name
        self.position = None  # 'long', 'short', None
        self.entry_price = 0.0
        self.current_trades = []

    @abstractmethod
    def analyze(self, data: pd.DataFrame) -> Dict:
        """
        Анализ данных и генерация сигнала

        Args:
            data: DataFrame с данными OHLCV и индикаторами

        Returns:
            Словарь с сигналом и информацией
            {
                'signal': 'buy'/'sell'/'hold',
                'reason': 'описание причины',
                'confidence': 0.0-1.0,
                'indicators': {...}
            }
        """
        pass

    @abstractmethod
    def get_position_size(self, balance: float, price: float, risk_percent: float) -> float:
        """
        Расчет размера позиции

        Args:
            balance: Текущий баланс
            price: Текущая цена
            risk_percent: Процент риска

        Returns:
            Размер позиции
        """
        pass

    def calculate_stop_loss(self, entry_price: float, side: str, stop_loss_percent: float) -> float:
        """
        Расчет уровня стоп-лосс

        Args:
            entry_price: Цена входа
            side: Сторона (buy/sell)
            stop_loss_percent: Процент стоп-лосса

        Returns:
            Цена стоп-лосса
        """
        if side == 'buy':
            return entry_price * (1 - stop_loss_percent / 100)
        else:
            return entry_price * (1 + stop_loss_percent / 100)

    def calculate_take_profit(self, entry_price: float, side: str, take_profit_percent: float) -> float:
        """
        Расчет уровня тейк-профит

        Args:
            entry_price: Цена входа
            side: Сторона (buy/sell)
            take_profit_percent: Процент тейк-профита

        Returns:
            Цена тейк-профита
        """
        if side == 'buy':
            return entry_price * (1 + take_profit_percent / 100)
        else:
            return entry_price * (1 - take_profit_percent / 100)

    def check_exit_conditions(self, current_price: float, stop_loss: float, take_profit: float, side: str) -> Optional[str]:
        """
        Проверка условий выхода из позиции

        Args:
            current_price: Текущая цена
            stop_loss: Уровень стоп-лосс
            take_profit: Уровень тейк-профит
            side: Сторона позиции

        Returns:
            'stop_loss', 'take_profit' или None
        """
        if side == 'buy':
            if current_price <= stop_loss:
                return 'stop_loss'
            elif current_price >= take_profit:
                return 'take_profit'
        else:
            if current_price >= stop_loss:
                return 'stop_loss'
            elif current_price <= take_profit:
                return 'take_profit'

        return None

    def get_info(self) -> Dict:
        """
        Получение информации о стратегии

        Returns:
            Словарь с информацией
        """
        return {
            'name': self.name,
            'position': self.position,
            'entry_price': self.entry_price,
            'active_trades': len(self.current_trades)
        }
