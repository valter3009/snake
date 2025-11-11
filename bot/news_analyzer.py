"""
Анализ и оценка важности новостей через Claude API
"""
import logging
import json
from typing import List, Dict, Any
from difflib import SequenceMatcher

from anthropic import AsyncAnthropic

import bot.config
from bot.news_collector import NewsArticle

logger = logging.getLogger(__name__)


class NewsAnalyzer:
    """Анализатор новостей с использованием Claude API"""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=bot.config.config.ANTHROPIC_API_KEY)

    async def analyze_and_rank_news(self, news_list: List[NewsArticle]) -> List[NewsArticle]:
        """
        Анализ списка новостей и выбор топовых

        Args:
            news_list: Список новостей

        Returns:
            Список топ-новостей (до TOP_NEWS_COUNT)
        """
        if not news_list:
            logger.warning("Пустой список новостей для анализа")
            return []

        logger.info(f"Анализируем {len(news_list)} новостей...")

        # Группируем дубликаты
        grouped_news = await self._group_duplicates(news_list)
        logger.info(f"После группировки дубликатов: {len(grouped_news)} новостей")

        # Оцениваем важность через Claude
        ranked_news = await self._rank_news_with_claude(grouped_news)

        # Возвращаем топ-N новостей
        top_news = ranked_news[:bot.config.config.TOP_NEWS_COUNT]
        logger.info(f"Выбрано {len(top_news)} топовых новостей")

        return top_news

    async def _group_duplicates(self, news_list: List[NewsArticle]) -> List[NewsArticle]:
        """
        Группировка дубликатов (новости с похожими заголовками)

        Args:
            news_list: Список новостей

        Returns:
            Список новостей с объединенными дубликатами
        """
        if not news_list:
            return []

        grouped = []
        processed_indices = set()

        for i, news in enumerate(news_list):
            if i in processed_indices:
                continue

            # Ищем похожие новости
            similar_news = [news]
            for j, other_news in enumerate(news_list):
                if i == j or j in processed_indices:
                    continue

                similarity = self._calculate_similarity(news.title, other_news.title)
                if similarity >= bot.config.config.DUPLICATE_THRESHOLD / 100.0:
                    similar_news.append(other_news)
                    processed_indices.add(j)

            # Если нашли похожие новости, объединяем их
            if len(similar_news) > 1:
                merged_news = await self._merge_news(similar_news)
                grouped.append(merged_news)
            else:
                grouped.append(news)

            processed_indices.add(i)

        return grouped

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Вычисление схожести двух текстов

        Args:
            text1: Первый текст
            text2: Второй текст

        Returns:
            Коэффициент схожести (0.0 - 1.0)
        """
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    async def _merge_news(self, news_list: List[NewsArticle]) -> NewsArticle:
        """
        Объединение нескольких похожих новостей в одну

        Args:
            news_list: Список похожих новостей

        Returns:
            Объединенная новость
        """
        logger.info(f"Объединяем {len(news_list)} похожих новостей")

        # Формируем промпт для Claude
        news_data = []
        for news in news_list:
            news_data.append({
                'source': news.source,
                'title': news.title,
                'description': news.description,
                'content': news.content[:500] if news.content else ''  # Ограничиваем контент
            })

        prompt = f"""Перед тобой несколько новостей об одном событии из разных источников.
Объедини информацию из всех источников в одну полную новость.

Новости:
{json.dumps(news_data, ensure_ascii=False, indent=2)}

Верни результат в формате JSON:
{{
    "title": "Объединенный заголовок (самый информативный)",
    "description": "Объединенное описание с деталями из всех источников",
    "content": "Полный текст с лучшими деталями из всех источников"
}}
"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            result_text = response.content[0].text
            # Извлекаем JSON из ответа
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            merged_data = json.loads(result_text)

            # Берем первую новость как базу и обновляем её
            base_news = news_list[0]
            base_news.title = merged_data.get('title', base_news.title)
            base_news.description = merged_data.get('description', base_news.description)
            base_news.content = merged_data.get('content', base_news.content)

            # Берем лучшее изображение (не пустое)
            for news in news_list:
                if news.image_url:
                    base_news.image_url = news.image_url
                    break

            return base_news

        except Exception as e:
            logger.error(f"Ошибка объединения новостей через Claude: {e}")
            # В случае ошибки возвращаем первую новость
            return news_list[0]

    async def _rank_news_with_claude(self, news_list: List[NewsArticle]) -> List[NewsArticle]:
        """
        Ранжирование новостей по важности через Claude

        Args:
            news_list: Список новостей

        Returns:
            Отсортированный список новостей (от важных к менее важным)
        """
        if not news_list:
            return []

        logger.info(f"Ранжируем {len(news_list)} новостей через Claude...")

        # Формируем список новостей для анализа
        news_data = []
        for idx, news in enumerate(news_list):
            news_data.append({
                'id': idx,
                'source': news.source,
                'title': news.title,
                'description': news.description[:300] if news.description else ''
            })

        prompt = f"""Ты - эксперт по новостям. Оцени важность и интересность каждой новости по шкале от 1 до 10.

Критерии оценки:
1. Масштаб события (международный/федеральный - выше, региональный - ниже)
2. Тип новости (breaking news - выше, аналитика/слухи - ниже)
3. Резонанс (упоминается в нескольких источниках - выше)
4. Необычность (неожиданные повороты - выше)
5. Актуальность (свежесть - выше)

Тематические приоритеты:
- Политика: 70% (высокий приоритет)
- Экономика: 15% (средний приоритет)
- Технологии/наука: 10% (средний приоритет)
- Общество: 5% (низкий приоритет)

География:
- Россия: 60% (высокий приоритет)
- Мир (США, Европа): 30% (средний приоритет)
- СНГ: 10% (низкий приоритет)

Что НЕ публикуем (оценка 1-3):
- Сплетни про знаменитостей
- Спорт (кроме крупных событий: Олимпиада, ЧМ)
- Криминал местного масштаба
- Погода/ЧП местного масштаба

Новости:
{json.dumps(news_data, ensure_ascii=False, indent=2)}

Верни результат в формате JSON - массив объектов с id и score (оценка 1-10):
[
    {{"id": 0, "score": 8, "reason": "Краткое объяснение оценки"}},
    {{"id": 1, "score": 6, "reason": "Краткое объяснение оценки"}},
    ...
]
"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            result_text = response.content[0].text
            # Извлекаем JSON из ответа
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            scores = json.loads(result_text)

            # Создаем словарь оценок
            score_dict = {item['id']: item['score'] for item in scores}

            # Сортируем новости по оценке
            sorted_news = sorted(
                news_list,
                key=lambda news: score_dict.get(news_list.index(news), 0),
                reverse=True
            )

            logger.info(f"Новости отранжированы. Топ-3 оценки: {[score_dict.get(news_list.index(news), 0) for news in sorted_news[:3]]}")

            return sorted_news

        except Exception as e:
            logger.error(f"Ошибка ранжирования новостей через Claude: {e}")
            # В случае ошибки возвращаем как есть
            return news_list


# Глобальный объект анализатора
news_analyzer = None


def init_news_analyzer() -> NewsAnalyzer:
    """
    Инициализация глобального анализатора новостей

    Returns:
        NewsAnalyzer
    """
    global news_analyzer
    news_analyzer = NewsAnalyzer()
    return news_analyzer
