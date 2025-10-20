"""
Модуль логирования для торгового бота IDTrade
"""

import logging
import colorlog
import os
from datetime import datetime


def setup_logger(name: str = "IDTrade", log_file: str = None, log_level: str = "INFO") -> logging.Logger:
    """
    Настройка цветного логгера

    Args:
        name: Имя логгера
        log_file: Путь к файлу логов
        log_level: Уровень логирования

    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Очистка существующих обработчиков
    logger.handlers = []

    # Формат для консоли с цветами
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Файловый обработчик
    if log_file:
        # Создание директории для логов
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def log_trade(logger: logging.Logger, trade_type: str, symbol: str, amount: float, price: float):
    """
    Логирование торговой операции

    Args:
        logger: Логгер
        trade_type: Тип операции (BUY/SELL)
        symbol: Торговая пара
        amount: Количество
        price: Цена
    """
    logger.info(f"TRADE: {trade_type} {amount} {symbol} @ {price}")


def log_signal(logger: logging.Logger, signal_type: str, symbol: str, reason: str):
    """
    Логирование торгового сигнала

    Args:
        logger: Логгер
        signal_type: Тип сигнала (BUY/SELL/HOLD)
        symbol: Торговая пара
        reason: Причина сигнала
    """
    logger.info(f"SIGNAL: {signal_type} for {symbol} - {reason}")


def log_error(logger: logging.Logger, error: Exception, context: str = ""):
    """
    Логирование ошибки с контекстом

    Args:
        logger: Логгер
        error: Исключение
        context: Контекст ошибки
    """
    if context:
        logger.error(f"{context}: {str(error)}", exc_info=True)
    else:
        logger.error(str(error), exc_info=True)
