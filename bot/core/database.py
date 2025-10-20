"""
Модуль базы данных для хранения истории сделок
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional


class TradingDatabase:
    """Класс для работы с базой данных торговых операций"""

    def __init__(self, db_path: str = "bot/data/trades.db"):
        """
        Инициализация базы данных

        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self._ensure_db_exists()
        self._create_tables()

    def _ensure_db_exists(self):
        """Создание директории для базы данных"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def _create_tables(self):
        """Создание таблиц в базе данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Таблица сделок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    cost REAL NOT NULL,
                    fee REAL,
                    pnl REAL,
                    strategy TEXT,
                    mode TEXT,
                    notes TEXT
                )
            ''')

            # Таблица баланса
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    balance REAL NOT NULL,
                    equity REAL NOT NULL,
                    mode TEXT NOT NULL
                )
            ''')

            # Таблица сигналов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    reason TEXT,
                    indicators TEXT,
                    executed INTEGER DEFAULT 0
                )
            ''')

            conn.commit()

    def add_trade(self, symbol: str, side: str, amount: float, price: float,
                  cost: float, fee: float = 0.0, pnl: Optional[float] = None,
                  strategy: str = "unknown", mode: str = "simulation",
                  notes: str = "") -> int:
        """
        Добавление сделки в базу данных

        Args:
            symbol: Торговая пара
            side: Сторона (buy/sell)
            amount: Количество
            price: Цена
            cost: Стоимость сделки
            fee: Комиссия
            pnl: Прибыль/убыток
            strategy: Название стратегии
            mode: Режим (simulation/live)
            notes: Заметки

        Returns:
            ID созданной записи
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (timestamp, symbol, side, amount, price, cost, fee, pnl, strategy, mode, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), symbol, side, amount, price, cost, fee, pnl, strategy, mode, notes))
            conn.commit()
            return cursor.lastrowid

    def add_balance_record(self, balance: float, equity: float, mode: str = "simulation"):
        """
        Добавление записи баланса

        Args:
            balance: Баланс
            equity: Капитал
            mode: Режим торговли
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO balance_history (timestamp, balance, equity, mode)
                VALUES (?, ?, ?, ?)
            ''', (datetime.now().isoformat(), balance, equity, mode))
            conn.commit()

    def add_signal(self, symbol: str, signal_type: str, reason: str = "",
                   indicators: str = "", executed: int = 0):
        """
        Добавление торгового сигнала

        Args:
            symbol: Торговая пара
            signal_type: Тип сигнала (BUY/SELL/HOLD)
            reason: Причина сигнала
            indicators: Значения индикаторов (JSON)
            executed: Флаг исполнения
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals (timestamp, symbol, signal_type, reason, indicators, executed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), symbol, signal_type, reason, indicators, executed))
            conn.commit()

    def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Получение истории сделок

        Args:
            symbol: Фильтр по торговой паре
            limit: Максимальное количество записей

        Returns:
            Список сделок
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if symbol:
                cursor.execute('''
                    SELECT * FROM trades WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?
                ''', (symbol, limit))
            else:
                cursor.execute('''
                    SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_balance_history(self, limit: int = 100) -> List[Dict]:
        """
        Получение истории баланса

        Args:
            limit: Максимальное количество записей

        Returns:
            Список записей баланса
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM balance_history ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_signals(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Получение истории сигналов

        Args:
            symbol: Фильтр по торговой паре
            limit: Максимальное количество записей

        Returns:
            Список сигналов
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if symbol:
                cursor.execute('''
                    SELECT * FROM signals WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?
                ''', (symbol, limit))
            else:
                cursor.execute('''
                    SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self, symbol: Optional[str] = None) -> Dict:
        """
        Получение статистики торговли

        Args:
            symbol: Фильтр по торговой паре

        Returns:
            Словарь со статистикой
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if symbol:
                cursor.execute('''
                    SELECT
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buy_trades,
                        SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sell_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as profitable_trades,
                        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                        SUM(pnl) as total_pnl,
                        AVG(pnl) as avg_pnl,
                        MAX(pnl) as max_pnl,
                        MIN(pnl) as min_pnl
                    FROM trades WHERE symbol = ?
                ''', (symbol,))
            else:
                cursor.execute('''
                    SELECT
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buy_trades,
                        SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sell_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as profitable_trades,
                        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                        SUM(pnl) as total_pnl,
                        AVG(pnl) as avg_pnl,
                        MAX(pnl) as max_pnl,
                        MIN(pnl) as min_pnl
                    FROM trades
                ''')

            row = cursor.fetchone()
            if row:
                return {
                    'total_trades': row[0] or 0,
                    'buy_trades': row[1] or 0,
                    'sell_trades': row[2] or 0,
                    'profitable_trades': row[3] or 0,
                    'losing_trades': row[4] or 0,
                    'total_pnl': row[5] or 0.0,
                    'avg_pnl': row[6] or 0.0,
                    'max_pnl': row[7] or 0.0,
                    'min_pnl': row[8] or 0.0,
                    'win_rate': (row[3] / row[0] * 100) if row[0] > 0 else 0.0
                }
            return {}
