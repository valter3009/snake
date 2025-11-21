"""
Форматирование контента для Telegram (Markdown)
"""
import re
from typing import Optional
from bot.core.logger import get_logger

logger = get_logger(__name__)


class ContentFormatter:
    """
    Форматирование контента для публикации в Telegram
    """

    def __init__(self):
        """Инициализация форматтера"""
        logger.info("🔧 ContentFormatter инициализирован")

    def format_for_telegram(self, content: str, add_source: bool = True) -> str:
        """
        Форматировать контент для Telegram (MarkdownV2)

        Args:
            content: Исходный текст
            add_source: Добавить ссылку на источник

        Returns:
            Отформатированный текст
        """
        # Убираем лишние переводы строк
        formatted = re.sub(r'\n{3,}', '\n\n', content)

        # Убираем пробелы в конце строк
        formatted = '\n'.join([line.rstrip() for line in formatted.split('\n')])

        # Ограничиваем длину (Telegram лимит ~4096 символов)
        if len(formatted) > 4000:
            formatted = formatted[:3997] + "..."
            logger.warning("⚠️ Пост обрезан до 4000 символов")

        return formatted.strip()

    def escape_markdown_v2(self, text: str) -> str:
        """
        Экранировать спецсимволы для MarkdownV2

        Args:
            text: Исходный текст

        Returns:
            Экранированный текст
        """
        # Символы, которые нужно экранировать в MarkdownV2
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

        for char in special_chars:
            text = text.replace(char, f'\\{char}')

        return text

    def clean_html_tags(self, text: str) -> str:
        """
        Удалить HTML теги из текста

        Args:
            text: Текст с HTML тегами

        Returns:
            Очищенный текст
        """
        # Удаляем HTML теги
        cleaned = re.sub(r'<[^>]+>', '', text)

        # Декодируем HTML entities
        import html
        cleaned = html.unescape(cleaned)

        return cleaned

    def add_channel_branding(self, content: str, channel_name: Optional[str] = None) -> str:
        """
        Добавить брендинг канала

        Args:
            content: Контент поста
            channel_name: Название канала

        Returns:
            Контент с брендингом
        """
        branding = "\n\n━━━━━━━━━━━━━━━━━━"

        if channel_name:
            branding += f"\n📢 {channel_name}"

        return content + branding

    def truncate_text(self, text: str, max_length: int = 500, suffix: str = "...") -> str:
        """
        Обрезать текст с умным переносом

        Args:
            text: Исходный текст
            max_length: Максимальная длина
            suffix: Суффикс для обрезанного текста

        Returns:
            Обрезанный текст
        """
        if len(text) <= max_length:
            return text

        # Обрезаем по последнему пробелу или точке
        truncated = text[:max_length]

        # Ищем последнюю точку или пробел
        last_period = truncated.rfind('.')
        last_space = truncated.rfind(' ')

        cut_point = max(last_period, last_space)

        if cut_point > max_length * 0.7:  # Если нашли достаточно близко к концу
            truncated = truncated[:cut_point]

        return truncated.rstrip() + suffix

    def count_words(self, text: str) -> int:
        """
        Подсчитать количество слов в тексте

        Args:
            text: Текст

        Returns:
            Количество слов
        """
        # Убираем Markdown разметку для точного подсчета
        clean_text = re.sub(r'\*\*', '', text)
        clean_text = re.sub(r'\*', '', clean_text)

        words = clean_text.split()
        return len(words)

    def validate_post_length(self, content: str, min_words: int = 300, max_words: int = 700) -> bool:
        """
        Проверить длину поста

        Args:
            content: Контент поста
            min_words: Минимальное количество слов
            max_words: Максимальное количество слов

        Returns:
            True если длина в пределах нормы
        """
        word_count = self.count_words(content)

        if word_count < min_words:
            logger.warning(f"⚠️ Пост слишком короткий: {word_count} слов (минимум {min_words})")
            return False
        elif word_count > max_words:
            logger.warning(f"⚠️ Пост слишком длинный: {word_count} слов (максимум {max_words})")
            return False

        return True
