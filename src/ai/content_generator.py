"""
Генератор контента - оркестрирует создание сообщений через Claude API.

Объединяет промпты, данные и Claude API для генерации уникального контента.
"""

from typing import Optional
from ai.claude_client import claude_client
from ai.prompts import (
    WHALE_ALERT_PROMPT,
    LISTING_PROMPT,
    MARKET_OVERVIEW_PROMPT,
    FEAR_GREED_PROMPT,
    AIRDROP_PROMPT
)
from utils.logger import get_logger

logger = get_logger(__name__)


class ContentGenerator:
    """
    Генерирует уникальный контент для разных типов событий.

    Использует Claude API для создания экспертных сообщений.
    Имеет fallback шаблоны на случай недоступности API.
    """

    def __init__(self):
        """Инициализирует генератор контента."""
        self.claude = claude_client

    async def generate_whale_alert(self, data: dict) -> Optional[str]:
        """
        Генерирует сообщение о движении кита.

        Args:
            data: Данные транзакции

        Returns:
            str: Сгенерированное сообщение
        """
        message = await self.claude.generate_content(WHALE_ALERT_PROMPT, data)

        if not message:
            # Fallback на простой шаблон
            message = self._whale_alert_fallback(data)

        return message

    async def generate_listing_alert(self, data: dict) -> Optional[str]:
        """
        Генерирует сообщение о новом листинге.

        Args:
            data: Данные листинга

        Returns:
            str: Сгенерированное сообщение
        """
        message = await self.claude.generate_content(LISTING_PROMPT, data)

        if not message:
            message = self._listing_alert_fallback(data)

        return message

    async def generate_market_overview(self, data: dict) -> Optional[str]:
        """
        Генерирует рыночный обзор.

        Args:
            data: Рыночные данные

        Returns:
            str: Сгенерированное сообщение
        """
        message = await self.claude.generate_content(MARKET_OVERVIEW_PROMPT, data)

        if not message:
            message = self._market_overview_fallback(data)

        return message

    async def generate_fear_greed_alert(self, data: dict) -> Optional[str]:
        """
        Генерирует анализ индекса страха/жадности.

        Args:
            data: Данные индекса

        Returns:
            str: Сгенерированное сообщение
        """
        message = await self.claude.generate_content(FEAR_GREED_PROMPT, data)

        if not message:
            message = self._fear_greed_fallback(data)

        return message

    # Fallback шаблоны на случай недоступности Claude API

    def _whale_alert_fallback(self, data: dict) -> str:
        """Простой шаблон для движения кита."""
        return f"""
🐋 **КРУПНАЯ ТРАНЗАКЦИЯ ОБНАРУЖЕНА**

💰 **Сумма:** ${data.get('amount_usd', 0):,.0f} ({data.get('amount_crypto', 0):.2f} {data.get('symbol', '')})

📍 **Направление:**
• Откуда: {data.get('from_owner', 'Неизвестно')}
• Куда: {data.get('to_owner', 'Неизвестно')}

⏰ **Время:** {data.get('timestamp', 'N/A')}

💵 **Текущая цена {data.get('symbol', '')}:** ${data.get('current_price', 0):,.2f}

━━━━━━━━━━━━━━━━━━━━
⚠️ Не является финансовым советом. Информация в ознакомительных целях.
Всегда проводите собственное исследование (DYOR).
"""

    def _listing_alert_fallback(self, data: dict) -> str:
        """Простой шаблон для листинга."""
        return f"""
🆕 **НОВЫЙ ЛИСТИНГ**

📛 **Проект:** {data.get('name', 'N/A')} ({data.get('symbol', 'N/A')})
🏦 **Биржа:** {data.get('exchange', 'N/A')}

📊 **Данные:**
• Market Cap: ${data.get('market_cap', 0):,.0f}
• Категория: {data.get('category', 'N/A')}
• Цена: ${data.get('price', 0):.4f}
• Изменение 1ч: {data.get('change_1h', 0):+.2f}%

━━━━━━━━━━━━━━━━━━━━
⚠️ Не является финансовым советом. Новые листинги высоковолатильны.
DYOR перед инвестированием.
"""

    def _market_overview_fallback(self, data: dict) -> str:
        """Простой шаблон для рыночного обзора."""
        return f"""
📊 **{data.get('period', '').upper()} РЫНОЧНЫЙ ОБЗОР**

**Bitcoin (BTC)**
💰 ${data.get('btc_price', 0):,.2f} ({data.get('btc_change', 0):+.2f}%)

**Ethereum (ETH)**
💰 ${data.get('eth_price', 0):,.2f} ({data.get('eth_change', 0):+.2f}%)

**Общая статистика:**
• Market Cap: ${data.get('total_mcap', 0):,.0f}
• BTC Dominance: {data.get('btc_dominance', 0):.1f}%
• Fear & Greed: {data.get('fear_greed', 'N/A')}

**Топ памперы:**
{data.get('gainers_data', 'N/A')}

**Топ дамперы:**
{data.get('losers_data', 'N/A')}

━━━━━━━━━━━━━━━━━━━━
⚠️ Не является финансовым советом. DYOR.
"""

    def _fear_greed_fallback(self, data: dict) -> str:
        """Простой шаблон для индекса страха/жадности."""
        change = data.get('current_value', 0) - data.get('previous_value', 0)

        return f"""
📊 **ИНДЕКС СТРАХА И ЖАДНОСТИ**

**Текущее значение:** {data.get('current_value', 0)}/100
**Классификация:** {data.get('classification', 'N/A')}

**Изменения:**
• За 24ч: {data.get('change_24h', 0):+d} пунктов
• За 7д: {data.get('change_7d', 0):+d} пунктов

**Предыдущее значение:** {data.get('previous_value', 0)}/100

━━━━━━━━━━━━━━━━━━━━
⚠️ Не является финансовым советом. DYOR.
"""
