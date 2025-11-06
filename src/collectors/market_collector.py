"""
Коллектор рыночных данных - цены, объемы, изменения.

Использует публичный API CoinGecko для получения данных о криптовалютах.
"""

from typing import List, Dict, Optional
from collectors.base_collector import BaseCollector
from utils.validators import validate_market_data


class MarketCollector(BaseCollector):
    """
    Собирает рыночные данные из CoinGecko API.

    Endpoints:
    - /coins/markets - список криптовалют с ценами и изменениями
    - /simple/price - текущие цены
    - /global - глобальная статистика рынка
    """

    def __init__(self):
        super().__init__("MarketCollector")
        self.base_url = "https://api.coingecko.com/api/v3"

    async def collect_data(self) -> List[Dict]:
        """
        Собирает общие рыночные данные.

        Returns:
            List[Dict]: Список с рыночной статистикой
        """
        data = []

        # Получаем данные о топ криптовалютах
        top_coins = await self.get_top_coins(limit=100)
        if top_coins:
            data.extend(top_coins)

        # Получаем глобальную статистику
        global_stats = await self.get_global_stats()
        if global_stats:
            data.append(global_stats)

        self.log_success(f"Собрано {len(data)} рыночных данных")
        return data

    async def get_top_coins(self, limit: int = 100) -> List[Dict]:
        """
        Получает данные о топ криптовалютах.

        Args:
            limit: Количество криптовалют

        Returns:
            List[Dict]: Список данных о криптовалютах
        """
        url = f"{self.base_url}/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': limit,
            'page': 1,
            'sparkline': False,
            'price_change_percentage': '1h,24h,7d'
        }

        data = await self.fetch_json(url, params)

        if not data:
            self.log_error("Не удалось получить данные о криптовалютах")
            return []

        # Парсим и валидируем данные
        coins = []
        for coin in data:
            try:
                coin_data = {
                    'id': coin.get('id'),
                    'symbol': coin.get('symbol', '').upper(),
                    'name': coin.get('name'),
                    'current_price': coin.get('current_price'),
                    'market_cap': coin.get('market_cap'),
                    'total_volume': coin.get('total_volume'),
                    'price_change_1h': coin.get('price_change_percentage_1h_in_currency'),
                    'price_change_24h': coin.get('price_change_percentage_24h_in_currency'),
                    'price_change_7d': coin.get('price_change_percentage_7d_in_currency'),
                    'market_cap_rank': coin.get('market_cap_rank'),
                }

                if validate_market_data(coin_data):
                    coins.append(coin_data)

            except Exception as e:
                self.log_warning(f"Ошибка парсинга данных монеты: {e}")
                continue

        return coins

    async def get_global_stats(self) -> Optional[Dict]:
        """
        Получает глобальную статистику рынка.

        Returns:
            Dict или None: Глобальная статистика
        """
        url = f"{self.base_url}/global"
        data = await self.fetch_json(url)

        if not data or 'data' not in data:
            self.log_error("Не удалось получить глобальную статистику")
            return None

        global_data = data['data']

        return {
            'type': 'global_stats',
            'total_market_cap': global_data.get('total_market_cap', {}).get('usd'),
            'total_volume': global_data.get('total_volume', {}).get('usd'),
            'btc_dominance': global_data.get('market_cap_percentage', {}).get('btc'),
            'eth_dominance': global_data.get('market_cap_percentage', {}).get('eth'),
            'active_cryptocurrencies': global_data.get('active_cryptocurrencies'),
            'markets': global_data.get('markets'),
        }

    async def get_coin_price(self, symbol: str) -> Optional[float]:
        """
        Получает текущую цену конкретной криптовалюты.

        Args:
            symbol: Символ криптовалюты (BTC, ETH, etc.)

        Returns:
            float или None: Цена в USD
        """
        # CoinGecko использует ID, а не символы
        # Упрощенное сопоставление для популярных монет
        symbol_to_id = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'USDT': 'tether',
            'USDC': 'usd-coin',
            'BNB': 'binancecoin',
            'XRP': 'ripple',
            'SOL': 'solana',
            'ADA': 'cardano',
        }

        coin_id = symbol_to_id.get(symbol.upper())
        if not coin_id:
            self.log_warning(f"Неизвестный символ: {symbol}")
            return None

        url = f"{self.base_url}/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd'
        }

        data = await self.fetch_json(url, params)

        if data and coin_id in data:
            return data[coin_id].get('usd')

        return None

    async def get_top_gainers_losers(self, limit: int = 5) -> Dict:
        """
        Получает топ памперов и дамперов.

        Args:
            limit: Количество монет в каждой категории

        Returns:
            Dict: {'gainers': [...], 'losers': [...]}
        """
        coins = await self.get_top_coins(limit=100)

        if not coins:
            return {'gainers': [], 'losers': []}

        # Сортируем по изменению за 24ч
        gainers = sorted(
            [c for c in coins if c.get('price_change_24h')],
            key=lambda x: x.get('price_change_24h', 0),
            reverse=True
        )[:limit]

        losers = sorted(
            [c for c in coins if c.get('price_change_24h')],
            key=lambda x: x.get('price_change_24h', 0)
        )[:limit]

        return {
            'gainers': gainers,
            'losers': losers
        }
