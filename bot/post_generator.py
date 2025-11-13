"""
Генерация постов для Telegram через Claude API
"""
import logging
import json
import random
import html
from typing import Dict, Any, List

from anthropic import AsyncAnthropic

import bot.config
from bot.news_collector import NewsArticle

logger = logging.getLogger(__name__)


class TelegramPost:
    """Класс для представления поста в Telegram"""

    def __init__(self, text: str, image_urls: List[str] = None, news_url: str = None, source: str = None):
        self.text = text
        self.image_urls = image_urls or []  # Теперь список изображений
        self.image_url = image_urls[0] if image_urls else None  # Для обратной совместимости
        self.news_url = news_url
        self.source = source

    def __repr__(self):
        return f"<TelegramPost(text_length={len(self.text)}, images_count={len(self.image_urls)})>"


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

        # Выбираем формат поста
        post_format = self._weighted_choice(self.post_formats)

        # Выбираем длину поста
        post_length = self._weighted_choice(self.post_lengths)

        # Генерируем пост через Claude
        post_text = await self._generate_with_claude(news, post_format, post_length)

        # Собираем все доступные изображения
        image_urls = []
        if hasattr(news, 'image_urls') and news.image_urls:
            image_urls = news.image_urls[:4]  # Максимум 4 изображения для медиагруппы
        elif news.image_url:
            image_urls = [news.image_url]

        # Создаем объект поста
        post = TelegramPost(
            text=post_text,
            image_urls=image_urls,
            news_url=news.url,
            source=news.source
        )

        logger.info(f"Пост сгенерирован: {len(post_text)} символов, {len(image_urls)} изображений")
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

        prompt = f"""Ты - автор инсайдерского Telegram-канала "Insider alert🚨". Напиши короткий живой пост о новости.

НОВОСТЬ:
Заголовок: {news.title}
Описание: {news.description}
Контент: {news.content[:500] if news.content else ''}

ТРЕБОВАНИЯ:
1. Длина: {post_length['description']} (МАКСИМУМ!)
2. Стиль: как будто пишет реальный человек, заметивший что-то важное
3. Эмодзи: {"1-2 символа максимум" if use_emoji else "без эмодзи"}
4. Markdown: используй **жирный** для акцентов
5. БЕЗ шаблонных фраз типа "новость дня", "сегодня стало известно", "по последним данным"
6. БЕЗ вступлений и заголовков - сразу к сути

КАК ПИСАТЬ:
- Начинай прямо с факта или инсайта
- Пиши коротко и ёмко
- Используй разговорный язык
- Если есть цифры - обязательно укажи
- Если скандал или противоречие - покажи обе стороны
- НЕ добавляй свои комментарии в конце

ЗАПРЕЩЕНО использовать:
❌ "Новость дня"
❌ "Стало известно"
❌ "По последним данным"
❌ "Сегодня"
❌ "Недавно"
❌ Любые клише

Верни ТОЛЬКО текст поста, ничего больше."""

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

            # Очищаем HTML entities (lquo, rquo и т.д.)
            post_text = html.unescape(post_text)

            # Заменяем проблемные символы
            post_text = post_text.replace('&lquo;', '"').replace('&rquo;', '"')
            post_text = post_text.replace('&ldquo;', '"').replace('&rdquo;', '"')
            post_text = post_text.replace('&nbsp;', ' ')
            post_text = post_text.replace('&mdash;', '—').replace('&ndash;', '–')

            # Добавляем ссылку на канал внизу
            channel_link = "\n\n📢 @InsidealeRT"
            post_text = post_text + channel_link

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
