"""
Основной класс торгового бота IDTrade
"""

import asyncio
import os
from typing import Dict, Optional
from datetime import datetime
import yaml
from dotenv import load_dotenv

from .exchange import SimulationExchange, ExchangeManager
from .database import TradingDatabase
from .logger import setup_logger, log_trade, log_signal
from ..strategies.rsi_ma_strategy import RSIMAStrategy


class TradingBot:
    """Основной класс торгового бота"""

    def __init__(self, config_path: str = "bot/config/config.yaml"):
        """
        Инициализация бота

        Args:
            config_path: Путь к конфигурационному файлу
        """
        # Загрузка переменных окружения
        load_dotenv()

        # Загрузка конфигурации
        self.config = self._load_config(config_path)

        # Настройка логгера
        self.logger = setup_logger(
            name="IDTrade",
            log_file=self.config['logging']['file'],
            log_level=self.config['logging']['level']
        )

        # Инициализация базы данных
        self.database = TradingDatabase(self.config['database']['path'])

        # Инициализация биржи
        trading_mode = self.config['trading']['mode']
        if trading_mode == 'simulation':
            self.exchange = SimulationExchange(
                initial_balance=self.config['simulation']['initial_balance'],
                fee_percent=self.config['simulation']['fee_percent']
            )
            self.logger.info(f"Бот запущен в режиме СИМУЛЯЦИИ с балансом {self.config['simulation']['initial_balance']} USDT")
        else:
            api_key = os.getenv('MEXC_API_KEY', '')
            api_secret = os.getenv('MEXC_API_SECRET', '')
            self.exchange = ExchangeManager(
                api_key=api_key,
                api_secret=api_secret,
                sandbox=self.config['exchange'].get('sandbox', False)
            )
            self.logger.warning("Бот запущен в РЕАЛЬНОМ режиме!")

        # Инициализация стратегии
        self.strategy = RSIMAStrategy(
            rsi_period=self.config['strategy']['rsi']['period'],
            rsi_oversold=self.config['strategy']['rsi']['oversold'],
            rsi_overbought=self.config['strategy']['rsi']['overbought'],
            ma_short_period=self.config['strategy']['ma']['short_period'],
            ma_long_period=self.config['strategy']['ma']['long_period']
        )

        # Состояние бота
        self.is_running = False
        self.current_positions = {}
        self.daily_trades_count = 0
        self.start_time = None

    def _load_config(self, config_path: str) -> Dict:
        """
        Загрузка конфигурации из YAML файла

        Args:
            config_path: Путь к файлу конфигурации

        Returns:
            Словарь с конфигурацией
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
            # Возврат конфигурации по умолчанию
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Конфигурация по умолчанию"""
        return {
            'trading': {'mode': 'simulation', 'pairs': ['BTC/USDT'], 'timeframe': '1h'},
            'strategy': {
                'rsi': {'period': 14, 'oversold': 30, 'overbought': 70},
                'ma': {'short_period': 20, 'long_period': 50}
            },
            'risk_management': {
                'max_position_size': 0.1,
                'stop_loss_percent': 2.0,
                'take_profit_percent': 5.0,
                'max_daily_trades': 10,
                'max_open_positions': 3
            },
            'simulation': {'initial_balance': 1000.0, 'fee_percent': 0.1},
            'database': {'path': 'bot/data/trades.db'},
            'logging': {'level': 'INFO', 'file': 'bot/logs/bot.log'},
            'exchange': {'name': 'mexc', 'sandbox': False}
        }

    async def run(self):
        """Главный цикл работы бота"""
        self.is_running = True
        self.start_time = datetime.now()
        self.logger.info("Бот IDTrade запущен!")

        try:
            while self.is_running:
                for symbol in self.config['trading']['pairs']:
                    await self.process_symbol(symbol)

                # Пауза между итерациями
                await asyncio.sleep(60)  # 1 минута

        except Exception as e:
            self.logger.error(f"Критическая ошибка в главном цикле: {e}", exc_info=True)
        finally:
            self.is_running = False
            self.logger.info("Бот остановлен")

    async def process_symbol(self, symbol: str):
        """
        Обработка торговой пары

        Args:
            symbol: Торговая пара (например, 'BTC/USDT')
        """
        try:
            # Получение данных
            timeframe = self.config['trading']['timeframe']
            data = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=100)

            if data.empty:
                self.logger.warning(f"Нет данных для {symbol}")
                return

            # Анализ стратегией
            signal = self.strategy.analyze(data)

            # Логирование сигнала
            log_signal(self.logger, signal['signal'], symbol, signal['reason'])

            # Сохранение сигнала в БД
            self.database.add_signal(
                symbol=symbol,
                signal_type=signal['signal'].upper(),
                reason=signal['reason'],
                indicators=str(signal['indicators'])
            )

            # Выполнение сделки
            if signal['signal'] == 'buy':
                await self.execute_buy(symbol, signal)
            elif signal['signal'] == 'sell':
                await self.execute_sell(symbol, signal)

            # Проверка существующих позиций
            if symbol in self.current_positions:
                await self.check_position(symbol, data)

        except Exception as e:
            self.logger.error(f"Ошибка обработки {symbol}: {e}", exc_info=True)

    async def execute_buy(self, symbol: str, signal: Dict):
        """
        Выполнение покупки

        Args:
            symbol: Торговая пара
            signal: Сигнал от стратегии
        """
        # Проверка ограничений
        if self.daily_trades_count >= self.config['risk_management']['max_daily_trades']:
            self.logger.info(f"Достигнут лимит дневных сделок ({self.daily_trades_count})")
            return

        if len(self.current_positions) >= self.config['risk_management']['max_open_positions']:
            self.logger.info(f"Достигнут лимит открытых позиций ({len(self.current_positions)})")
            return

        if symbol in self.current_positions:
            self.logger.info(f"Позиция по {symbol} уже открыта")
            return

        try:
            # Получение баланса
            balance_info = await self.exchange.fetch_balance()
            usdt_balance = balance_info['free'].get('USDT', 0)

            # Расчет размера позиции
            current_price = signal['indicators']['price']
            position_size = self.strategy.get_position_size(
                usdt_balance,
                current_price,
                self.config['risk_management']['max_position_size']
            )

            if position_size * current_price > usdt_balance:
                self.logger.warning(f"Недостаточно средств для покупки {symbol}")
                return

            # Выполнение ордера
            order = await self.exchange.create_market_order(symbol, 'buy', position_size)

            # Логирование
            log_trade(self.logger, 'BUY', symbol, position_size, current_price)

            # Сохранение в БД
            self.database.add_trade(
                symbol=symbol,
                side='buy',
                amount=position_size,
                price=current_price,
                cost=position_size * current_price,
                fee=order['fee']['cost'] if 'fee' in order else 0,
                strategy=self.strategy.name,
                mode=self.config['trading']['mode']
            )

            # Сохранение позиции
            self.current_positions[symbol] = {
                'side': 'buy',
                'entry_price': current_price,
                'amount': position_size,
                'stop_loss': self.strategy.calculate_stop_loss(
                    current_price, 'buy',
                    self.config['risk_management']['stop_loss_percent']
                ),
                'take_profit': self.strategy.calculate_take_profit(
                    current_price, 'buy',
                    self.config['risk_management']['take_profit_percent']
                )
            }

            self.daily_trades_count += 1
            self.logger.info(f"Открыта позиция BUY: {position_size} {symbol} @ {current_price}")

        except Exception as e:
            self.logger.error(f"Ошибка выполнения покупки {symbol}: {e}", exc_info=True)

    async def execute_sell(self, symbol: str, signal: Dict):
        """
        Выполнение продажи

        Args:
            symbol: Торговая пара
            signal: Сигнал от стратегии
        """
        if symbol not in self.current_positions:
            self.logger.info(f"Нет открытой позиции по {symbol} для продажи")
            return

        try:
            position = self.current_positions[symbol]
            current_price = signal['indicators']['price']

            # Выполнение ордера
            order = await self.exchange.create_market_order(symbol, 'sell', position['amount'])

            # Расчет P&L
            pnl = (current_price - position['entry_price']) * position['amount']

            # Логирование
            log_trade(self.logger, 'SELL', symbol, position['amount'], current_price)

            # Сохранение в БД
            self.database.add_trade(
                symbol=symbol,
                side='sell',
                amount=position['amount'],
                price=current_price,
                cost=position['amount'] * current_price,
                fee=order['fee']['cost'] if 'fee' in order else 0,
                pnl=pnl,
                strategy=self.strategy.name,
                mode=self.config['trading']['mode']
            )

            # Закрытие позиции
            del self.current_positions[symbol]
            self.daily_trades_count += 1

            self.logger.info(f"Закрыта позиция SELL: {position['amount']} {symbol} @ {current_price}, P&L: {pnl:.2f}")

        except Exception as e:
            self.logger.error(f"Ошибка выполнения продажи {symbol}: {e}", exc_info=True)

    async def check_position(self, symbol: str, data):
        """
        Проверка текущей позиции на стоп-лосс и тейк-профит

        Args:
            symbol: Торговая пара
            data: Данные OHLCV
        """
        if symbol not in self.current_positions:
            return

        position = self.current_positions[symbol]
        current_price = data['close'].iloc[-1]

        # Проверка стоп-лосс и тейк-профит
        exit_reason = self.strategy.check_exit_conditions(
            current_price,
            position['stop_loss'],
            position['take_profit'],
            position['side']
        )

        if exit_reason:
            self.logger.info(f"Триггер выхода для {symbol}: {exit_reason}")
            # Генерация сигнала на продажу
            signal = {
                'signal': 'sell',
                'reason': f'Триггер {exit_reason}',
                'indicators': {'price': current_price}
            }
            await self.execute_sell(symbol, signal)

    def get_status(self) -> Dict:
        """Получение статуса бота"""
        return {
            'status': 'running' if self.is_running else 'stopped',
            'mode': self.config['trading']['mode'],
            'symbol': ', '.join(self.config['trading']['pairs']),
            'open_positions': len(self.current_positions),
            'daily_trades': self.daily_trades_count,
            'uptime': str(datetime.now() - self.start_time) if self.start_time else '0:00:00'
        }

    async def get_balance(self) -> Dict:
        """Получение баланса"""
        try:
            balance_info = await self.exchange.fetch_balance()
            balances = balance_info['free']

            # Расчет эквити для симуляции
            if hasattr(self.exchange, 'get_equity'):
                prices = {}
                for symbol in self.config['trading']['pairs']:
                    ticker = await self.exchange.fetch_ticker(symbol)
                    prices[symbol] = ticker['last']
                equity = self.exchange.get_equity(prices)
            else:
                equity = balances.get('USDT', 0)

            return {
                'USDT': balances.get('USDT', 0),
                'BTC': balances.get('BTC', 0),
                'equity': equity
            }
        except Exception as e:
            self.logger.error(f"Ошибка получения баланса: {e}")
            return {}

    def get_config(self) -> Dict:
        """Получение конфигурации"""
        return self.config

    def stop(self):
        """Остановка бота"""
        self.is_running = False
        self.logger.info("Получена команда на остановку бота")
