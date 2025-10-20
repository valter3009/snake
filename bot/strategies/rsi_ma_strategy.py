"""
Торговая стратегия на основе RSI и Moving Average
"""

import pandas as pd
from typing import Dict
from .base_strategy import BaseStrategy
from .indicators import calculate_rsi, calculate_ma


class RSIMAStrategy(BaseStrategy):
    """
    Стратегия на основе RSI и скользящих средних

    Правила:
    - BUY: RSI < oversold И короткая MA > длинной MA
    - SELL: RSI > overbought И короткая MA < длинной MA
    """

    def __init__(self,
                 rsi_period: int = 14,
                 rsi_oversold: int = 30,
                 rsi_overbought: int = 70,
                 ma_short_period: int = 20,
                 ma_long_period: int = 50):
        """
        Инициализация стратегии

        Args:
            rsi_period: Период для RSI
            rsi_oversold: Уровень перепроданности
            rsi_overbought: Уровень перекупленности
            ma_short_period: Период короткой MA
            ma_long_period: Период длинной MA
        """
        super().__init__(name="RSI_MA_Strategy")

        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.ma_short_period = ma_short_period
        self.ma_long_period = ma_long_period

    def analyze(self, data: pd.DataFrame) -> Dict:
        """
        Анализ данных и генерация торгового сигнала

        Args:
            data: DataFrame с данными OHLCV

        Returns:
            Словарь с сигналом и информацией
        """
        # Проверка минимального количества данных
        if len(data) < max(self.rsi_period, self.ma_long_period):
            return {
                'signal': 'hold',
                'reason': 'Недостаточно данных для анализа',
                'confidence': 0.0,
                'indicators': {}
            }

        # Расчет индикаторов
        rsi = calculate_rsi(data, self.rsi_period)
        ma_short = calculate_ma(data, self.ma_short_period)
        ma_long = calculate_ma(data, self.ma_long_period)

        # Получение последних значений
        current_rsi = rsi.iloc[-1]
        current_ma_short = ma_short.iloc[-1]
        current_ma_long = ma_long.iloc[-1]
        current_price = data['close'].iloc[-1]

        # Словарь с индикаторами
        indicators = {
            'rsi': float(current_rsi),
            'ma_short': float(current_ma_short),
            'ma_long': float(current_ma_long),
            'price': float(current_price)
        }

        # Генерация сигнала
        signal = 'hold'
        reason = ''
        confidence = 0.0

        # Проверка условий для покупки
        if current_rsi < self.rsi_oversold and current_ma_short > current_ma_long:
            signal = 'buy'
            reason = f'RSI {current_rsi:.2f} ниже уровня перепроданности {self.rsi_oversold}, MA короткая выше длинной'
            confidence = self._calculate_confidence(current_rsi, current_ma_short, current_ma_long, 'buy')

        # Проверка условий для продажи
        elif current_rsi > self.rsi_overbought and current_ma_short < current_ma_long:
            signal = 'sell'
            reason = f'RSI {current_rsi:.2f} выше уровня перекупленности {self.rsi_overbought}, MA короткая ниже длинной'
            confidence = self._calculate_confidence(current_rsi, current_ma_short, current_ma_long, 'sell')

        # Дополнительные условия для hold
        else:
            if current_ma_short > current_ma_long:
                reason = f'Восходящий тренд (MA короткая > длинной), но RSI {current_rsi:.2f} не в зоне перепроданности'
            elif current_ma_short < current_ma_long:
                reason = f'Нисходящий тренд (MA короткая < длинной), но RSI {current_rsi:.2f} не в зоне перекупленности'
            else:
                reason = 'Нет четкого тренда, ожидание сигнала'

        return {
            'signal': signal,
            'reason': reason,
            'confidence': confidence,
            'indicators': indicators
        }

    def _calculate_confidence(self, rsi: float, ma_short: float, ma_long: float, signal_type: str) -> float:
        """
        Расчет уверенности в сигнале (0.0 - 1.0)

        Args:
            rsi: Значение RSI
            ma_short: Короткая MA
            ma_long: Длинная MA
            signal_type: Тип сигнала (buy/sell)

        Returns:
            Уровень уверенности
        """
        confidence = 0.0

        if signal_type == 'buy':
            # Чем ниже RSI, тем выше уверенность
            rsi_confidence = (self.rsi_oversold - rsi) / self.rsi_oversold
            rsi_confidence = max(0, min(1, rsi_confidence))

            # Чем больше разрыв между MA, тем выше уверенность
            ma_diff = (ma_short - ma_long) / ma_long * 100
            ma_confidence = min(1, ma_diff / 5)  # 5% разрыв = макс уверенность

            confidence = (rsi_confidence + ma_confidence) / 2

        elif signal_type == 'sell':
            # Чем выше RSI, тем выше уверенность
            rsi_confidence = (rsi - self.rsi_overbought) / (100 - self.rsi_overbought)
            rsi_confidence = max(0, min(1, rsi_confidence))

            # Чем больше разрыв между MA, тем выше уверенность
            ma_diff = (ma_long - ma_short) / ma_long * 100
            ma_confidence = min(1, ma_diff / 5)

            confidence = (rsi_confidence + ma_confidence) / 2

        return round(confidence, 2)

    def get_position_size(self, balance: float, price: float, risk_percent: float) -> float:
        """
        Расчет размера позиции на основе процента баланса

        Args:
            balance: Текущий баланс
            price: Текущая цена
            risk_percent: Процент от баланса для торговли

        Returns:
            Размер позиции (количество монет)
        """
        # Максимальная сумма для инвестирования
        max_investment = balance * risk_percent

        # Размер позиции
        position_size = max_investment / price

        return round(position_size, 8)

    def should_close_position(self, data: pd.DataFrame, entry_price: float, side: str) -> tuple[bool, str]:
        """
        Проверка, нужно ли закрывать позицию

        Args:
            data: DataFrame с данными
            entry_price: Цена входа
            side: Сторона позиции (buy/sell)

        Returns:
            Tuple (нужно_закрывать, причина)
        """
        # Расчет индикаторов
        rsi = calculate_rsi(data, self.rsi_period)
        ma_short = calculate_ma(data, self.ma_short_period)
        ma_long = calculate_ma(data, self.ma_long_period)

        current_rsi = rsi.iloc[-1]
        current_ma_short = ma_short.iloc[-1]
        current_ma_long = ma_long.iloc[-1]

        # Закрытие long позиции
        if side == 'buy':
            if current_rsi > self.rsi_overbought:
                return True, f'RSI {current_rsi:.2f} выше уровня перекупленности'
            if current_ma_short < current_ma_long:
                return True, 'Разворот тренда (MA короткая пересекла длинную вниз)'

        # Закрытие short позиции
        elif side == 'sell':
            if current_rsi < self.rsi_oversold:
                return True, f'RSI {current_rsi:.2f} ниже уровня перепроданности'
            if current_ma_short > current_ma_long:
                return True, 'Разворот тренда (MA короткая пересекла длинную вверх)'

        return False, ''
