"""
Коллектор индекса страха и жадности.

Использует публичный API Alternative.me для получения Fear & Greed Index.
"""

from typing import List, Dict, Optional
from collectors.base_collector import BaseCollector


class FearGreedCollector(BaseCollector):
    """
    Собирает данные индекса страха и жадности.

    API: https://api.alternative.me/fng/
    Полностью бесплатный, без лимитов.
    """

    def __init__(self):
        super().__init__("FearGreedCollector")
        self.base_url = "https://api.alternative.me/fng"

    async def collect_data(self) -> List[Dict]:
        """
        Собирает текущее значение индекса.

        Returns:
            List[Dict]: Список с данными индекса
        """
        current = await self.get_current_index()
        if current:
            return [current]
        return []

    async def get_current_index(self) -> Optional[Dict]:
        """
        Получает текущее значение индекса страха и жадности.

        Returns:
            Dict или None: Данные индекса
        """
        url = f"{self.base_url}/?limit=1"
        data = await self.fetch_json(url)

        if not data or 'data' not in data:
            self.log_error("Не удалось получить индекс страха и жадности")
            return None

        try:
            index_data = data['data'][0]

            result = {
                'type': 'fear_greed_index',
                'value': int(index_data['value']),
                'classification': index_data['value_classification'],
                'timestamp': index_data['timestamp']
            }

            self.log_success(f"Индекс: {result['value']} ({result['classification']})")
            return result

        except (KeyError, ValueError, IndexError) as e:
            self.log_error(f"Ошибка парсинга данных индекса", exc=e)
            return None

    async def get_history(self, days: int = 30) -> List[Dict]:
        """
        Получает историю индекса за последние N дней.

        Args:
            days: Количество дней истории

        Returns:
            List[Dict]: История значений индекса
        """
        url = f"{self.base_url}/?limit={days}"
        data = await self.fetch_json(url)

        if not data or 'data' not in data:
            self.log_error("Не удалось получить историю индекса")
            return []

        history = []
        for entry in data['data']:
            try:
                history.append({
                    'value': int(entry['value']),
                    'classification': entry['value_classification'],
                    'timestamp': entry['timestamp']
                })
            except (KeyError, ValueError) as e:
                continue

        return history

    def classify_value(self, value: int) -> str:
        """
        Классифицирует значение индекса.

        Args:
            value: Значение индекса (0-100)

        Returns:
            str: Классификация
        """
        if value <= 25:
            return "Extreme Fear"
        elif value <= 45:
            return "Fear"
        elif value <= 55:
            return "Neutral"
        elif value <= 75:
            return "Greed"
        else:
            return "Extreme Greed"
