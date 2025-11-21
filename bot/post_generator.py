"""
Генерация постов для Telegram через Claude API
"""
import logging
import json
import random
import html
from typing import Dict, Any

from anthropic import AsyncAnthropic

import bot.config
from bot.news_collector import NewsArticle
from bot.article_extractor import article_extractor

logger = logging.getLogger(__name__)


class TelegramPost:
    """Класс для представления поста в Telegram"""

    def __init__(self, text: str, image_url: str = None, video_url: str = None, news_url: str = None, source: str = None):
        self.text = text
        self.image_url = image_url
        self.video_url = video_url
        self.news_url = news_url
        self.source = source

    def __repr__(self):
        return f"<TelegramPost(text_length={len(self.text)}, has_image={bool(self.image_url)}, has_video={bool(self.video_url)})>"


class PostGenerator:
    """Генератор постов для Telegram"""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=bot.config.config.ANTHROPIC_API_KEY)

        # Форматы постов
        self.post_formats = [
            {
                'name': 'classic',
                'weight': 30,
                'template': '📰 Классическая новость с заголовком'
            },
            {
                'name': 'personal',
                'weight': 25,
                'template': '💬 "Заметил интересное..." (личный стиль)'
            },
            {
                'name': 'hot',
                'weight': 20,
                'template': '🔥 "Горячее: ..." (срочные новости)'
            },
            {
                'name': 'discussion',
                'weight': 15,
                'template': '🤔 "А что думаете о..." (провокация дискуссии)'
            },
            {
                'name': 'digest',
                'weight': 10,
                'template': '📊 "Коротко о главном" (дайджест)'
            }
        ]

        # Длина постов (по вероятности)
        self.post_lengths = [
            {'name': 'short', 'weight': 30, 'description': '2-3 предложения'},
            {'name': 'medium', 'weight': 50, 'description': 'один абзац'},
            {'name': 'long', 'weight': 20, 'description': '2-3 абзаца'}
        ]

    async def generate_post(self, news: NewsArticle) -> TelegramPost:
        """
        Генерация поста для новости

        Args:
            news: Объект новости

        Returns:
            Объект TelegramPost
        """
        logger.info(f"Генерируем пост для новости: {news.title[:50]}...")

        # Пытаемся получить полный текст статьи, если его еще нет
        if not news.content or len(news.content) < 500:
            logger.info("Извлекаем полный текст статьи...")
            full_text = await article_extractor.extract_article_text(news.url)
            if full_text:
                news.content = full_text
                logger.info(f"Полный текст получен: {len(full_text)} символов")

        # Выбираем формат поста
        post_format = self._weighted_choice(self.post_formats)

        # Выбираем длину поста
        post_length = self._weighted_choice(self.post_lengths)

        # Генерируем пост через Claude
        post_text = await self._generate_with_claude(news, post_format, post_length)

        # Создаем объект поста
        post = TelegramPost(
            text=post_text,
            image_url=news.image_url,
            video_url=news.video_url,
            news_url=news.url,
            source=news.source
        )

        logger.info(f"Пост сгенерирован: {len(post_text)} символов")
        return post

    def _weighted_choice(self, choices: list) -> dict:
        """
        Взвешенный выбор элемента из списка

        Args:
            choices: Список словарей с ключом 'weight'

        Returns:
            Выбранный элемент
        """
        total_weight = sum(choice['weight'] for choice in choices)
        r = random.uniform(0, total_weight)
        upto = 0

        for choice in choices:
            if upto + choice['weight'] >= r:
                return choice
            upto += choice['weight']

        return choices[0]

    async def _generate_with_claude(
        self,
        news: NewsArticle,
        post_format: dict,
        post_length: dict
    ) -> str:
        """
        Генерация текста поста через Claude API

        Args:
            news: Новость
            post_format: Формат поста
            post_length: Длина поста

        Returns:
            Текст поста
        """

        # Определяем, использовать ли эмодзи
        use_emoji = random.choice([True, True, False])  # 66% вероятность

        # Используем полный контент если доступен, иначе description
        full_content = news.content if news.content and len(news.content) > 200 else news.description

        prompt = f"""Ты - российский политический аналитик и блогер с критическим взглядом на события, пишущий в стиле Дмитрия Никотина. Твой стиль:
- Прямолинейный и откровенный анализ
- Критический, но обоснованный подход
- Ироничные комментарии там, где уместно
- Глубокое понимание контекста и подтекста событий
- Неформальный, но грамотный язык
- Объяснение "что это значит на самом деле" для читателя

НОВОСТЬ:
Заголовок: {news.title}
Описание: {news.description}
Полный текст: {full_content}
Источник: {news.source}

ТРЕБОВАНИЯ К ПОСТУ:
1. Формат: {post_format['template']}
2. Длина: {post_length['description']}
3. Стиль: как Дмитрий Никотин - аналитично, критично, с пониманием подтекста
4. Эмодзи: {"умеренно (1-2)" if use_emoji else "БЕЗ эмодзи"}
5. Markdown: используй **жирный** для ключевых моментов
6. НЕ добавляй ссылки на источники

СТРУКТУРА ПОСТА:
1. Суть новости (что случилось)
2. Контекст и подтекст (что это значит, почему важно)
3. Твой критический анализ или комментарий

ВАЖНО:
- Опирайся на ВСЮ информацию из полного текста, а не только на заголовок
- Раскрывай суть события, объясняй важные детали
- Критический анализ должен быть обоснованным
- Избегай конспирологии, но не бойся указывать на противоречия
- Пиши как эксперт, который видит больше, чем написано между строк

Верни ТОЛЬКО текст поста, без пояснений."""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                temperature=1.0,  # Высокая температура для разнообразия
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            post_text = response.content[0].text.strip()

            # Убираем возможные кавычки в начале и конце
            if post_text.startswith('"') and post_text.endswith('"'):
                post_text = post_text[1:-1]

            # Декодируем HTML-сущности (&nbsp;, &laquo;, &raquo;, etc)
            post_text = html.unescape(post_text)

            return post_text

        except Exception as e:
            logger.error(f"Ошибка генерации поста через Claude: {e}")
            # Fallback - простой пост
            return self._generate_fallback_post(news)

    def _generate_fallback_post(self, news: NewsArticle) -> str:
        """
        Генерация простого поста в случае ошибки API

        Args:
            news: Новость

        Returns:
            Текст поста
        """
        templates = [
            f"**{news.title}**\n\n{news.description}",
            f"📰 {news.title}\n\n{news.description}",
            f"**Новость дня**\n\n{news.title}\n\n{news.description}"
        ]

        return random.choice(templates)

    async def generate_multiple_posts(self, news_list: list[NewsArticle]) -> list[TelegramPost]:
        """
        Генерация нескольких постов

        Args:
            news_list: Список новостей

        Returns:
            Список постов
        """
        posts = []

        for news in news_list:
            try:
                post = await self.generate_post(news)
                posts.append(post)
            except Exception as e:
                logger.error(f"Ошибка генерации поста для новости {news.title[:50]}: {e}")
                continue

        logger.info(f"Сгенерировано {len(posts)} постов из {len(news_list)} новостей")
        return posts


# Глобальный объект генератора
post_generator = None


def init_post_generator() -> PostGenerator:
    """
    Инициализация глобального генератора постов

    Returns:
        PostGenerator
    """
    global post_generator
    post_generator = PostGenerator()
    return post_generator
