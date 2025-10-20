"""
Модуль для работы с биржей MEXC через CCXT
"""

import ccxt
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime


class ExchangeManager:
    """Класс для работы с криптобиржей"""

    def __init__(self, api_key: str = "", api_secret: str = "", sandbox: bool = False):
        """
        Инициализация подключения к бирже

        Args:
            api_key: API ключ
            api_secret: API секрет
            sandbox: Использовать тестовую среду
        """
        self.exchange = ccxt.mexc({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })

        if sandbox:
            self.exchange.set_sandbox_mode(True)

    async def fetch_ticker(self, symbol: str) -> Dict:
        """
        Получение текущей цены

        Args:
            symbol: Торговая пара (например, 'BTC/USDT')

        Returns:
            Информация о тикере
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            raise Exception(f"Ошибка получения тикера: {str(e)}")

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """
        Получение OHLCV данных (свечи)

        Args:
            symbol: Торговая пара
            timeframe: Временной интервал
            limit: Количество свечей

        Returns:
            DataFrame с историческими данными
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            raise Exception(f"Ошибка получения OHLCV: {str(e)}")

    async def create_market_order(self, symbol: str, side: str, amount: float) -> Dict:
        """
        Создание рыночного ордера

        Args:
            symbol: Торговая пара
            side: Сторона (buy/sell)
            amount: Количество

        Returns:
            Информация об ордере
        """
        try:
            order = self.exchange.create_market_order(symbol, side, amount)
            return order
        except Exception as e:
            raise Exception(f"Ошибка создания ордера: {str(e)}")

    async def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Dict:
        """
        Создание лимитного ордера

        Args:
            symbol: Торговая пара
            side: Сторона (buy/sell)
            amount: Количество
            price: Цена

        Returns:
            Информация об ордере
        """
        try:
            order = self.exchange.create_limit_order(symbol, side, amount, price)
            return order
        except Exception as e:
            raise Exception(f"Ошибка создания лимитного ордера: {str(e)}")

    async def fetch_balance(self) -> Dict:
        """
        Получение баланса

        Returns:
            Информация о балансе
        """
        try:
            balance = self.exchange.fetch_balance()
            return balance
        except Exception as e:
            raise Exception(f"Ошибка получения баланса: {str(e)}")

    async def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """
        Получение информации об ордере

        Args:
            order_id: ID ордера
            symbol: Торговая пара

        Returns:
            Информация об ордере
        """
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            raise Exception(f"Ошибка получения ордера: {str(e)}")

    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """
        Отмена ордера

        Args:
            order_id: ID ордера
            symbol: Торговая пара

        Returns:
            Результат отмены
        """
        try:
            result = self.exchange.cancel_order(order_id, symbol)
            return result
        except Exception as e:
            raise Exception(f"Ошибка отмены ордера: {str(e)}")


class SimulationExchange:
    """Класс для симуляции торговли без реальных денег"""

    def __init__(self, initial_balance: float = 1000.0, fee_percent: float = 0.1):
        """
        Инициализация симулятора

        Args:
            initial_balance: Начальный баланс в USDT
            fee_percent: Процент комиссии
        """
        self.balance = {'USDT': initial_balance}
        self.fee_percent = fee_percent / 100
        self.orders = []
        self.exchange = ccxt.mexc({
            'enableRateLimit': True,
        })

    async def fetch_ticker(self, symbol: str) -> Dict:
        """Получение текущей цены (реальные данные)"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            raise Exception(f"Ошибка получения тикера: {str(e)}")

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Получение OHLCV данных (реальные данные)"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            raise Exception(f"Ошибка получения OHLCV: {str(e)}")

    async def create_market_order(self, symbol: str, side: str, amount: float) -> Dict:
        """
        Симуляция рыночного ордера

        Args:
            symbol: Торговая пара
            side: Сторона (buy/sell)
            amount: Количество

        Returns:
            Информация об ордере
        """
        try:
            ticker = await self.fetch_ticker(symbol)
            price = ticker['last']

            base, quote = symbol.split('/')

            if side == 'buy':
                cost = amount * price
                fee = cost * self.fee_percent
                total_cost = cost + fee

                if self.balance.get(quote, 0) < total_cost:
                    raise Exception(f"Недостаточно средств: требуется {total_cost} {quote}")

                self.balance[quote] = self.balance.get(quote, 0) - total_cost
                self.balance[base] = self.balance.get(base, 0) + amount

            elif side == 'sell':
                if self.balance.get(base, 0) < amount:
                    raise Exception(f"Недостаточно средств: требуется {amount} {base}")

                cost = amount * price
                fee = cost * self.fee_percent
                total_received = cost - fee

                self.balance[base] = self.balance.get(base, 0) - amount
                self.balance[quote] = self.balance.get(quote, 0) + total_received

            order = {
                'id': str(len(self.orders) + 1),
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'type': 'market',
                'side': side,
                'amount': amount,
                'price': price,
                'cost': amount * price,
                'fee': {'cost': cost * self.fee_percent, 'currency': quote},
                'status': 'closed'
            }

            self.orders.append(order)
            return order

        except Exception as e:
            raise Exception(f"Ошибка симуляции ордера: {str(e)}")

    async def fetch_balance(self) -> Dict:
        """Получение симулированного баланса"""
        return {
            'total': self.balance.copy(),
            'free': self.balance.copy(),
            'used': {k: 0.0 for k in self.balance.keys()}
        }

    def get_equity(self, prices: Dict[str, float]) -> float:
        """
        Расчет общего капитала в USDT

        Args:
            prices: Словарь с текущими ценами

        Returns:
            Общий капитал
        """
        equity = self.balance.get('USDT', 0)
        for currency, amount in self.balance.items():
            if currency != 'USDT' and amount > 0:
                symbol = f"{currency}/USDT"
                price = prices.get(symbol, 0)
                equity += amount * price
        return equity
