"""
Система логирования для бота.

Создает структурированные логи с цветным выводом в консоль и сохранением в файлы.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветным выводом для консоли.

    Разные уровни логов выводятся разными цветами для лучшей читаемости.
    """

    # ANSI коды цветов
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }

    def format(self, record):
        """Форматирует лог-запись с цветами."""
        # Добавляем цвет к уровню лога
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

        return super().format(record)


def setup_logger(
    name: str = 'crypto_bot',
    log_dir: str = './logs',
    level: str = 'INFO',
    console_output: bool = True
) -> logging.Logger:
    """
    Настраивает и возвращает логгер с файловым и консольным выводом.

    Args:
        name: Имя логгера
        log_dir: Директория для файлов логов
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Выводить ли логи в консоль

    Returns:
        logging.Logger: Настроенный логгер

    Example:
        >>> logger = setup_logger('my_module', level='DEBUG')
        >>> logger.info("Бот запущен!")
        >>> logger.error("Произошла ошибка", exc_info=True)
    """
    # Создаем директорию для логов если её нет
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Если логгер уже настроен, не добавляем дублирующие обработчики
    if logger.handlers:
        return logger

    # Формат для файлов: детальный с временем и именем модуля
    file_formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Формат для консоли: компактный с цветами
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )

    # Файловый обработчик с ротацией (максимум 10MB, 5 файлов)
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = log_path / f'{name}_{today}.log'

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # В файл пишем всё
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Консольный обработчик
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получает существующий логгер или создает новый.

    Args:
        name: Имя логгера (обычно __name__ модуля)

    Returns:
        logging.Logger: Логгер

    Example:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Модуль загружен")
    """
    return logging.getLogger(name)


# Создаем главный логгер при импорте модуля
main_logger = setup_logger()
