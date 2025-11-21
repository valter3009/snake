"""
Анализ новостей через Claude AI
"""
import asyncio
from typing import List, Dict, Any, Optional
from anthropic import AsyncAnthropic
from bot.core.logger import get_logger
from bot.core.exceptions import NewsAnalysisError

logger = get_logger(__name__)


class NewsAnalyzer:
    """
    Анализ новостей через Claude AI
    """

    def __init__(self, api_key: str):
        """
        Инициализация анализатора

        Args:
            api_key: API ключ Anthropic
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-latest"
        logger.info("🔧 NewsAnalyzer инициализирован (Claude AI)")

    async def select_top_news(
        self,
        news_list: List[Dict[str, Any]],
        top_count: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Отобрать самые важные новости для публикации

        Args:
            news_list: Список новостей
            top_count: Количество топовых новостей

        Returns:
            Список отобранных новостей
        """
        if not news_list:
            logger.warning("⚠️ Пустой список новостей для анализа")
            return []

        logger.info(f"🤖 Анализ {len(news_list)} новостей через Claude AI...")

        try:
            # Формируем список новостей для анализа
            news_summary = self._format_news_for_analysis(news_list)

            # Промпт для Claude
            prompt = f"""Ты - опытный политический редактор российского новостного канала.

Перед тобой список из {len(news_list)} новостей за последние часы.

КРИТЕРИИ ОТБОРА (по убыванию важности):
1. Политическая значимость для России
2. Влияние на экономику и жизнь граждан
3. Геополитическое значение
4. Потенциал для глубокого анализа
5. Актуальность и свежесть

ИСКЛЮЧИ:
- Развлекательные новости
- Спорт (кроме политически значимых)
- Мелкие происшествия
- Повторяющиеся темы

ОТБЕРИ {top_count} САМЫХ ВАЖНЫХ новостей для политического анализа.

НОВОСТИ:
{news_summary}

Ответь ТОЛЬКО JSON массивом с номерами выбранных новостей (от 1 до {len(news_list)}):
[1, 5, 12, 23, 45]"""

            # Запрос к Claude
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            # Парсим ответ
            response_text = message.content[0].text.strip()
            selected_indices = self._parse_selection(response_text)

            # Отбираем новости
            selected_news = []
            for idx in selected_indices[:top_count]:
                if 0 <= idx < len(news_list):
                    selected_news.append(news_list[idx])

            logger.info(f"✅ Отобрано топовых новостей: {len(selected_news)}")
            return selected_news

        except Exception as e:
            logger.error(f"❌ Ошибка при анализе новостей: {e}")
            # Fallback: берем первые N новостей
            return news_list[:top_count]

    def _format_news_for_analysis(self, news_list: List[Dict[str, Any]]) -> str:
        """
        Форматировать новости для анализа Claude

        Args:
            news_list: Список новостей

        Returns:
            Отформатированная строка
        """
        formatted = []
        for i, news in enumerate(news_list, 1):
            title = news.get('title', 'Без заголовка')
            source = news.get('source', 'Неизвестный источник')
            description = news.get('description', '')[:200]  # Первые 200 символов

            formatted.append(f"{i}. [{source}] {title}\n   {description}...")

        return '\n\n'.join(formatted)

    def _parse_selection(self, response: str) -> List[int]:
        """
        Распарсить выбор Claude

        Args:
            response: Ответ от Claude

        Returns:
            Список индексов (0-based)
        """
        try:
            # Находим JSON массив
            import re
            match = re.search(r'\[[\d,\s]+\]', response)
            if match:
                import json
                indices = json.loads(match.group())
                # Преобразуем в 0-based индексы
                return [idx - 1 for idx in indices if isinstance(idx, int)]
            else:
                logger.warning("⚠️ Не удалось распарсить выбор Claude")
                return []
        except Exception as e:
            logger.warning(f"⚠️ Ошибка парсинга выбора: {e}")
            return []

    async def analyze_news_importance(self, news_item: Dict[str, Any]) -> float:
        """
        Оценить важность отдельной новости (0.0 - 1.0)

        Args:
            news_item: Новость

        Returns:
            Оценка важности
        """
        try:
            title = news_item.get('title', '')
            description = news_item.get('description', '')

            prompt = f"""Оцени политическую важность этой новости для России по шкале от 0 до 10.

Новость: {title}
{description}

Ответь ТОЛЬКО числом от 0 до 10:"""

            message = await self.client.messages.create(
                model=self.model,
                max_tokens=10,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            score = float(response_text)
            return min(max(score / 10.0, 0.0), 1.0)

        except Exception as e:
            logger.warning(f"⚠️ Ошибка оценки важности новости: {e}")
            return 0.5  # Средняя важность по умолчанию
