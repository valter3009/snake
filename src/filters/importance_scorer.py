"""
Система оценки важности событий по шкале 0-10.

Публикуются только события с оценкой >= MIN_IMPORTANCE_SCORE (обычно 7).
Это ключевой компонент для "умной фильтрации" и сокращения спама.
"""

from datetime import datetime
from typing import Dict
from utils.logger import get_logger

logger = get_logger(__name__)


class ImportanceScorer:
    """
    Оценивает важность криптовалютных событий.

    Критерии оценки:
    - Размер/масштаб события (30%)
    - Влияние на рынок (25%)
    - Популярность актива (20%)
    - Новизна информации (15%)
    - Контекст рынка (10%)
    """

    def __init__(self):
        """Инициализирует оценщик важности."""
        # Популярные криптовалюты (вес в оценке)
        self.top_cryptos = {
            'BTC': 2.0,
            'ETH': 2.0,
            'USDT': 1.5,
            'USDC': 1.5,
            'BNB': 1.0,
            'XRP': 1.0,
            'SOL': 1.0,
            'ADA': 0.5,
        }

        # Топ биржи (вес в оценке)
        self.top_exchanges = {
            'Binance': 3.0,
            'Coinbase': 3.0,
            'Bybit': 2.0,
            'OKX': 2.0,
            'Kraken': 2.0,
        }

    def score_whale_transaction(self, tx: Dict) -> float:
        """
        Оценивает важность транзакции кита.

        Args:
            tx: Словарь с данными транзакции
                - amount_usd: Сумма в USD
                - symbol: Символ криптовалюты
                - from_exchange: Является ли отправитель биржей
                - to_exchange: Является ли получатель биржей

        Returns:
            float: Оценка важности (0-10)

        Example:
            >>> scorer = ImportanceScorer()
            >>> tx = {'amount_usd': 10000000, 'symbol': 'BTC', 'to_exchange': True}
            >>> score = scorer.score_whale_transaction(tx)
            >>> score >= 7
            True
        """
        score = 0.0
        amount = tx.get('amount_usd', 0)
        symbol = tx.get('symbol', '').upper()

        # 1. Размер транзакции (0-4 балла)
        if amount >= 50_000_000:
            score += 4
        elif amount >= 20_000_000:
            score += 3
        elif amount >= 10_000_000:
            score += 2
        elif amount >= 5_000_000:
            score += 1
        else:
            return 0  # Слишком мало для публикации

        # 2. Направление транзакции (0-2 балла)
        from_exchange = tx.get('from_exchange', False)
        to_exchange = tx.get('to_exchange', False)

        if to_exchange and not from_exchange:
            score += 2  # На биржу = возможна продажа (важнее)
        elif from_exchange and not to_exchange:
            score += 1  # С биржи = возможна покупка

        # 3. Популярность криптовалюты (0-2 балла)
        crypto_weight = self.top_cryptos.get(symbol, 0)
        score += min(crypto_weight, 2.0)

        # 4. Время суток (0-1 балл)
        # Во время торгов в США важнее
        current_hour = datetime.utcnow().hour
        if 13 <= current_hour <= 21:  # 9am-5pm EST
            score += 1

        # 5. Бонус за очень крупные суммы
        if amount >= 100_000_000:  # $100M+
            score += 1  # Дополнительный балл за экстремальный размер

        final_score = min(score, 10.0)  # Максимум 10
        logger.debug(f"Whale TX оценка: {final_score:.1f} (${amount:,.0f} {symbol})")
        return final_score

    def score_new_listing(self, listing: Dict) -> float:
        """
        Оценивает важность нового листинга.

        Args:
            listing: Словарь с данными листинга
                - exchange: Название биржи
                - market_cap: Рыночная капитализация
                - category: Категория проекта
                - vc_backed: Есть ли венчурное финансирование

        Returns:
            float: Оценка важности (0-10)

        Example:
            >>> scorer = ImportanceScorer()
            >>> listing = {
            ...     'exchange': 'Binance',
            ...     'market_cap': 500000000,
            ...     'category': 'Layer1',
            ...     'vc_backed': True
            ... }
            >>> score = scorer.score_new_listing(listing)
            >>> score >= 7
            True
        """
        score = 0.0
        exchange = listing.get('exchange', '')
        market_cap = listing.get('market_cap', 0)
        category = listing.get('category', '')

        # 1. Биржа (0-3 балла)
        exchange_weight = self.top_exchanges.get(exchange, 0)
        score += min(exchange_weight, 3.0)

        if exchange_weight == 0:
            # Листинги только на топ-5 биржах
            return 0

        # 2. Капитализация проекта (0-3 балла)
        if market_cap >= 1_000_000_000:  # $1B+
            score += 3
        elif market_cap >= 500_000_000:  # $500M+
            score += 2
        elif market_cap >= 100_000_000:  # $100M+
            score += 1
        else:
            return 0  # Слишком маленький проект

        # 3. Категория проекта (0-2 балла)
        important_categories = {
            'Layer1': 2.0,
            'Layer2': 2.0,
            'DeFi': 1.5,
            'Gaming': 1.0,
            'AI': 1.5,
            'RWA': 1.0,
        }
        category_weight = important_categories.get(category, 0.5)
        score += min(category_weight, 2.0)

        # 4. Венчурное финансирование (0-2 балла)
        if listing.get('vc_backed', False):
            funding = listing.get('funding_amount', 0)
            if funding >= 50_000_000:  # $50M+ финансирования
                score += 2
            else:
                score += 1

        final_score = min(score, 10.0)
        logger.debug(f"Listing оценка: {final_score:.1f} ({exchange})")
        return final_score

    def score_fear_greed_change(self, current_value: int, previous_value: int) -> float:
        """
        Оценивает важность изменения индекса страха/жадности.

        Args:
            current_value: Текущее значение (0-100)
            previous_value: Предыдущее значение

        Returns:
            float: Оценка важности (0-10)

        Example:
            >>> scorer = ImportanceScorer()
            >>> score = scorer.score_fear_greed_change(20, 45)  # Резкое падение
            >>> score >= 7
            True
        """
        score = 0.0

        # 1. Размер изменения (0-4 балла)
        change = abs(current_value - previous_value)
        if change >= 20:
            score += 4  # Очень значительное изменение
        elif change >= 15:
            score += 3
        elif change >= 10:
            score += 2
        else:
            return 0  # Изменение слишком маленькое

        # 2. Нахождение в экстремальных зонах (0-3 балла)
        if current_value <= 25:  # Extreme Fear
            score += 3
        elif current_value >= 75:  # Extreme Greed
            score += 3
        elif current_value <= 35:  # Fear
            score += 1
        elif current_value >= 65:  # Greed
            score += 1

        # 3. Направление изменения в экстремальных зонах (0-2 балла)
        if current_value <= 25 and previous_value > 25:
            score += 2  # Вошли в Extreme Fear
        elif current_value >= 75 and previous_value < 75:
            score += 2  # Вошли в Extreme Greed

        # 4. Разворот тренда (0-1 балл)
        if (previous_value < 50 <= current_value) or (previous_value >= 50 > current_value):
            score += 1  # Пересечение нейтральной зоны

        final_score = min(score, 10.0)
        logger.debug(f"Fear&Greed оценка: {final_score:.1f} ({previous_value}→{current_value})")
        return final_score

    def score_market_overview(self) -> float:
        """
        Оценивает важность рыночного обзора.

        Рыночные обзоры всегда публикуются в запланированное время,
        поэтому всегда возвращают высокую оценку.

        Returns:
            float: Всегда 10.0 (максимальная важность)
        """
        return 10.0  # Рыночные обзоры всегда публикуются

    def score_airdrop(self, airdrop: Dict) -> float:
        """
        Оценивает важность airdrop алерта.

        Args:
            airdrop: Словарь с данными airdrop
                - valuation: Оценка проекта
                - estimated_reward: Ожидаемая награда
                - reputation: Репутация проекта
                - effort_level: Уровень усилий (low/medium/high)

        Returns:
            float: Оценка важности (0-10)
        """
        score = 0.0

        # 1. Оценка проекта (0-3 балла)
        valuation = airdrop.get('valuation', 0)
        if valuation >= 1_000_000_000:  # $1B+
            score += 3
        elif valuation >= 500_000_000:  # $500M+
            score += 2
        elif valuation >= 100_000_000:  # $100M+
            score += 1
        else:
            return 0  # Слишком маленький проект

        # 2. Ожидаемая награда (0-3 балла)
        reward = airdrop.get('estimated_reward', 0)
        if reward >= 500:  # $500+
            score += 3
        elif reward >= 200:  # $200+
            score += 2
        elif reward >= 100:  # $100+
            score += 1

        # 3. Репутация проекта (0-2 балла)
        reputation = airdrop.get('reputation', 'unknown')
        if reputation == 'verified':
            score += 2
        elif reputation == 'known':
            score += 1

        # 4. Уровень усилий (0-2 балла) - проще = лучше
        effort = airdrop.get('effort_level', 'high')
        if effort == 'low':
            score += 2
        elif effort == 'medium':
            score += 1

        final_score = min(score, 10.0)
        logger.debug(f"Airdrop оценка: {final_score:.1f}")
        return final_score
