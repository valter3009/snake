"""
Настройка цветного логирования с эмодзи
"""
import logging
import colorlog
from typing import Optional


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Настройка цветного логирования с эмодзи

    Args:
        name: Имя логгера
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Настроенный логгер
    """

    # Создаем handler для вывода в консоль
    handler = colorlog.StreamHandler()

    # Устанавливаем форматтер с цветами
    handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    ))

    # Создаем и настраиваем логгер
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper()))

    return logger


# Глобальный логгер для быстрого доступа
_default_logger: Optional[logging.Logger] = None


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Получить логгер

    Args:
        name: Имя логгера (если None, используется дефолтный)

    Returns:
        Логгер
    """
    global _default_logger

    if name:
        return setup_logger(name)

    if _default_logger is None:
        _default_logger = setup_logger("bot")

    return _default_logger
