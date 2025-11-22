"""
Генерация аналитических постов через Claude AI
"""
from typing import Dict, Any, Optional
from anthropic import AsyncAnthropic
from bot.core.logger import get_logger
from bot.core.exceptions import ContentGenerationError
from bot.content.prompts import (
    ANALYST_PROMPT,
    SHORT_ANALYSIS_PROMPT,
    QUALITY_CHECK_PROMPT
)
from bot.content.formatter import ContentFormatter

logger = get_logger(__name__)


class ContentGenerator:
    """
    Генератор аналитического контента
    """

    def __init__(self, api_key: str):
        """
        Инициализация генератора

        Args:
            api_key: API ключ Anthropic
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20240620"
        self.formatter = ContentFormatter()
        logger.info("🔧 ContentGenerator инициализирован (Claude AI)")

    async def generate_post(
        self,
        news_item: Dict[str, Any],
        full_text: Optional[str] = None
    ) -> Optional[str]:
        """
        Сгенерировать аналитический пост из новости

        Args:
            news_item: Данные новости
            full_text: Полный текст новости (если извлечен)

        Returns:
            Сгенерированный пост или None при ошибке
        """
        try:
            title = news_item.get('title', '')
            source = news_item.get('source', '')
            published_at = news_item.get('published_at', '')
            description = news_item.get('description', '')

            logger.info(f"✍️ Генерация поста для: {title[:50]}...")

            # Выбираем промпт в зависимости от наличия полного текста
            if full_text and len(full_text) > 500:
                prompt = ANALYST_PROMPT.format(
                    title=title,
                    source=source,
                    published_at=published_at,
                    content=full_text[:5000]  # Ограничиваем для экономии токенов
                )
            else:
                # Используем короткий промпт если полного текста нет
                prompt = SHORT_ANALYSIS_PROMPT.format(
                    title=title,
                    description=description[:1000]
                )

            # Запрос к Claude
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )

            # Получаем сгенерированный контент
            generated_content = message.content[0].text.strip()

            # Форматируем для Telegram
            formatted_post = self.formatter.format_for_telegram(generated_content)

            # Проверяем качество
            if not self.formatter.validate_post_length(formatted_post, min_words=200, max_words=800):
                logger.warning("⚠️ Пост не прошел проверку длины")
                return None

            logger.info(f"✅ Пост сгенерирован ({self.formatter.count_words(formatted_post)} слов)")
            return formatted_post

        except Exception as e:
            logger.error(f"❌ Ошибка генерации поста: {e}")
            return None

    async def check_post_quality(self, content: str) -> float:
        """
        Проверить качество сгенерированного поста

        Args:
            content: Контент поста

        Returns:
            Оценка качества (0.0 - 1.0)
        """
        try:
            prompt = QUALITY_CHECK_PROMPT.format(content=content[:2000])

            message = await self.client.messages.create(
                model=self.model,
                max_tokens=10,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            score_text = message.content[0].text.strip()
            score = float(score_text)

            # Нормализуем к 0.0 - 1.0
            normalized_score = min(max(score / 10.0, 0.0), 1.0)

            logger.info(f"📊 Оценка качества поста: {score}/10")
            return normalized_score

        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки качества: {e}")
            return 0.5  # Средняя оценка по умолчанию

    async def generate_multiple_posts(
        self,
        news_list: list,
        full_texts: Optional[Dict[str, str]] = None
    ) -> list:
        """
        Сгенерировать несколько постов

        Args:
            news_list: Список новостей
            full_texts: Словарь {url: full_text}

        Returns:
            Список кортежей (news_item, generated_post)
        """
        posts = []

        for news_item in news_list:
            url = news_item.get('url', '')
            full_text = None

            if full_texts and url in full_texts:
                full_text = full_texts[url]

            post = await self.generate_post(news_item, full_text)

            if post:
                # Проверяем качество
                quality_score = await self.check_post_quality(post)

                if quality_score >= 0.6:  # Минимальный порог качества
                    posts.append((news_item, post))
                    logger.info(f"✅ Пост добавлен (качество: {quality_score:.2f})")
                else:
                    logger.warning(f"⚠️ Пост отклонен (низкое качество: {quality_score:.2f})")

        logger.info(f"✅ Сгенерировано постов: {len(posts)}/{len(news_list)}")
        return posts

    async def enhance_post(self, content: str) -> str:
        """
        Улучшить существующий пост

        Args:
            content: Исходный пост

        Returns:
            Улучшенный пост
        """
        try:
            prompt = f"""Улучши этот аналитический пост:

{content}

Сделай его более:
• Структурированным
• Убедительным
• Читабельным

Сохрани стиль и длину. Используй **жирный текст** для ключевых тезисов."""

            message = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.6,
                messages=[{"role": "user", "content": prompt}]
            )

            enhanced = message.content[0].text.strip()
            return self.formatter.format_for_telegram(enhanced)

        except Exception as e:
            logger.warning(f"⚠️ Ошибка улучшения поста: {e}")
            return content  # Возвращаем оригинал при ошибке
