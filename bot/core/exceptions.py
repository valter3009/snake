"""
Кастомные исключения для бота
"""


class BotError(Exception):
    """Базовое исключение для бота"""
    pass


class ConfigError(BotError):
    """Ошибка конфигурации"""
    pass


class DatabaseError(BotError):
    """Ошибка работы с базой данных"""
    pass


class NewsCollectionError(BotError):
    """Ошибка сбора новостей"""
    pass


class NewsAnalysisError(BotError):
    """Ошибка анализа новостей"""
    pass


class ContentGenerationError(BotError):
    """Ошибка генерации контента"""
    pass


class PublishError(BotError):
    """Ошибка публикации"""
    pass


class MediaError(BotError):
    """Ошибка обработки медиа"""
    pass
