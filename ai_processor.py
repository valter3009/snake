"""
Модуль для обработки текстов новостей через Claude API
Генерация привлекательных постов для Telegram канала
"""

import logging
import re
from typing import Dict, Optional
from anthropic import Anthropic

from config import (
    ANTHROPIC_API_KEY,
    CLAUDE_PROMPT_TEMPLATE,
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    CLAUDE_TEMPERATURE
)

logger = logging.getLogger(__name__)


class AIProcessor:
    """Класс для обработки текстов через Claude API"""

    def __init__(self):
        """Инициализация клиента Claude API"""
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY не установлен в переменных окружения")

        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info("AI Processor инициализирован")

    def generate_post_text(self, news_item: Dict) -> Optional[Dict]:
        """
        Генерация текста поста для Telegram на основе новости

        Args:
            news_item: Словарь с данными новости

        Returns:
            Словарь с заголовком, описанием и хештегами или None
        """
        try:
            # Формирование промпта
            prompt = CLAUDE_PROMPT_TEMPLATE.format(
                title=news_item.get('title', ''),
                description=news_item.get('description', '')[:500],  # Ограничиваем длину
                source=news_item.get('source', 'Неизвестный источник')
            )

            logger.info(f"Отправка запроса к Claude API для новости: {news_item['title'][:50]}...")

            # Запрос к Claude API
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                temperature=CLAUDE_TEMPERATURE,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Извлечение текста ответа
            response_text = response.content[0].text

            # Парсинг ответа
            parsed_post = self._parse_claude_response(response_text)

            if parsed_post:
                logger.info(f"Пост успешно сгенерирован: {parsed_post['title'][:50]}...")
                return parsed_post
            else:
                logger.warning("Не удалось распарсить ответ Claude")
                return None

        except Exception as e:
            logger.error(f"Ошибка при обращении к Claude API: {e}")
            return None

    def _parse_claude_response(self, response_text: str) -> Optional[Dict]:
        """
        Парсинг ответа от Claude API

        Args:
            response_text: Текст ответа от Claude

        Returns:
            Словарь с заголовком, описанием и хештегами или None
        """
        try:
            # Поиск компонентов с помощью регулярных выражений
            title_match = re.search(r'Заголовок:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
            description_match = re.search(r'Описание:\s*(.+?)(?:\nХештеги:|$)', response_text, re.IGNORECASE | re.DOTALL)
            hashtags_match = re.search(r'Хештеги:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)

            if not title_match or not description_match:
                logger.warning("Не удалось найти заголовок или описание в ответе")
                return None

            title = title_match.group(1).strip()
            description = description_match.group(1).strip()
            hashtags = hashtags_match.group(1).strip() if hashtags_match else ''

            # Очистка от лишних символов
            title = self._clean_text(title)
            description = self._clean_text(description)
            hashtags = self._clean_hashtags(hashtags)

            return {
                'title': title,
                'description': description,
                'hashtags': hashtags
            }

        except Exception as e:
            logger.error(f"Ошибка парсинга ответа Claude: {e}")
            return None

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Очистка текста от лишних символов

        Args:
            text: Исходный текст

        Returns:
            Очищенный текст
        """
        # Удаление кавычек в начале и конце
        text = text.strip('"\'')

        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    @staticmethod
    def _clean_hashtags(hashtags: str) -> str:
        """
        Очистка и форматирование хештегов

        Args:
            hashtags: Строка с хештегами

        Returns:
            Форматированные хештеги
        """
        # Удаление лишних символов
        hashtags = hashtags.strip('"\'')

        # Проверка наличия символа #
        tags = hashtags.split()
        cleaned_tags = []

        for tag in tags:
            tag = tag.strip()
            if tag and not tag.startswith('#'):
                tag = '#' + tag
            if tag:
                cleaned_tags.append(tag)

        return ' '.join(cleaned_tags)

    def format_telegram_post(self, post_data: Dict, source: str = '') -> str:
        """
        Форматирование финального поста для Telegram

        Args:
            post_data: Словарь с данными поста
            source: Источник новости (опционально)

        Returns:
            Форматированный текст поста
        """
        # Выбор эмодзи для заголовка (если его еще нет)
        title = post_data['title']
        if not any(char in title for char in ['🔥', '⚡', '💡', '🚀', '📰', '🎯']):
            # Если в заголовке нет эмодзи, добавляем подходящий
            title = f"🔥 {title}"

        # Формирование поста
        post_parts = [
            title,
            '',
            post_data['description']
        ]

        # Добавление хештегов
        if post_data.get('hashtags'):
            post_parts.append('')
            post_parts.append(post_data['hashtags'])

        # Добавление источника (опционально)
        if source:
            post_parts.append('')
            post_parts.append(f"📌 Источник: {source}")

        return '\n'.join(post_parts)

    def test_connection(self) -> bool:
        """
        Тестирование подключения к Claude API

        Returns:
            True если подключение успешно
        """
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=50,
                messages=[
                    {
                        "role": "user",
                        "content": "Привет! Ответь одним словом: работает"
                    }
                ]
            )

            result = response.content[0].text
            logger.info(f"Тест подключения к Claude API: {result}")
            return True

        except Exception as e:
            logger.error(f"Ошибка тестирования Claude API: {e}")
            return False
