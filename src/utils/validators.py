"""
Валидаторы для проверки данных из внешних API.

Защита от невалидных данных и потенциальных атак.
"""

import re
from typing import Any, Optional
from decimal import Decimal


def is_valid_crypto_symbol(symbol: str) -> bool:
    """
    Проверяет что символ криптовалюты валидный.

    Args:
        symbol: Символ криптовалюты (например: BTC, ETH)

    Returns:
        bool: True если валидный, False иначе

    Example:
        >>> is_valid_crypto_symbol('BTC')
        True
        >>> is_valid_crypto_symbol('123')
        False
        >>> is_valid_crypto_symbol('<script>alert(1)</script>')
        False
    """
    if not symbol or not isinstance(symbol, str):
        return False

    # Символы должны быть 2-10 символов, только буквы и цифры
    pattern = r'^[A-Z0-9]{2,10}$'
    return bool(re.match(pattern, symbol.upper()))


def is_valid_address(address: str, blockchain: str = 'ethereum') -> bool:
    """
    Проверяет валидность адреса кошелька.

    Args:
        address: Адрес кошелька
        blockchain: Название блокчейна (ethereum, bitcoin, etc.)

    Returns:
        bool: True если адрес выглядит валидным

    Example:
        >>> is_valid_address('0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb')
        True
        >>> is_valid_address('invalid')
        False
    """
    if not address or not isinstance(address, str):
        return False

    if blockchain.lower() == 'ethereum':
        # Ethereum адрес: 0x + 40 hex символов
        pattern = r'^0x[a-fA-F0-9]{40}$'
        return bool(re.match(pattern, address))

    elif blockchain.lower() == 'bitcoin':
        # Bitcoin адрес: различные форматы (упрощенная проверка)
        pattern = r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$'
        return bool(re.match(pattern, address))

    # Для остальных блокчейнов - базовая проверка
    return len(address) >= 20 and address.isalnum()


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    Очищает строку от потенциально опасных символов.

    Args:
        text: Исходная строка
        max_length: Максимальная длина результата

    Returns:
        str: Очищенная строка

    Example:
        >>> sanitize_string('<script>alert("xss")</script>')
        'scriptalert("xss")/script'
        >>> sanitize_string('Normal text 123')
        'Normal text 123'
    """
    if not text or not isinstance(text, str):
        return ""

    # Удаляем HTML теги
    text = re.sub(r'<[^>]+>', '', text)

    # Ограничиваем длину
    text = text[:max_length]

    return text.strip()


def is_valid_amount(amount: Any, min_value: float = 0, max_value: Optional[float] = None) -> bool:
    """
    Проверяет что сумма валидная.

    Args:
        amount: Сумма для проверки
        min_value: Минимальное допустимое значение
        max_value: Максимальное допустимое значение (опционально)

    Returns:
        bool: True если сумма валидная

    Example:
        >>> is_valid_amount(1000)
        True
        >>> is_valid_amount(-100)
        False
        >>> is_valid_amount(50, min_value=100)
        False
    """
    try:
        # Преобразуем в Decimal для точности
        amount_decimal = Decimal(str(amount))

        # Проверяем диапазон
        if amount_decimal < Decimal(str(min_value)):
            return False

        if max_value is not None and amount_decimal > Decimal(str(max_value)):
            return False

        # Проверяем что не NaN или Infinity
        if not amount_decimal.is_finite():
            return False

        return True

    except (ValueError, TypeError, ArithmeticError):
        return False


def is_valid_percentage(value: Any) -> bool:
    """
    Проверяет что значение является валидным процентом.

    Args:
        value: Значение процента

    Returns:
        bool: True если валидный процент

    Example:
        >>> is_valid_percentage(50.5)
        True
        >>> is_valid_percentage(-10)
        True
        >>> is_valid_percentage('not a number')
        False
    """
    try:
        percent = float(value)
        # Разумные границы: от -1000% до +10000%
        return -1000 <= percent <= 10000
    except (ValueError, TypeError):
        return False


def is_valid_url(url: str) -> bool:
    """
    Проверяет что URL валидный и безопасный.

    Args:
        url: URL для проверки

    Returns:
        bool: True если URL валидный

    Example:
        >>> is_valid_url('https://api.coingecko.com/api/v3/ping')
        True
        >>> is_valid_url('javascript:alert(1)')
        False
    """
    if not url or not isinstance(url, str):
        return False

    # Разрешаем только http и https
    pattern = r'^https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=]+$'

    if not re.match(pattern, url):
        return False

    # Блокируем опасные схемы
    dangerous_schemes = ['javascript:', 'data:', 'file:', 'vbscript:']
    url_lower = url.lower()
    for scheme in dangerous_schemes:
        if url_lower.startswith(scheme):
            return False

    return True


def validate_market_data(data: dict) -> bool:
    """
    Проверяет что данные о рынке валидны.

    Args:
        data: Словарь с рыночными данными

    Returns:
        bool: True если данные валидны

    Example:
        >>> data = {'symbol': 'BTC', 'price': 43000, 'volume': 1000000}
        >>> validate_market_data(data)
        True
    """
    if not isinstance(data, dict):
        return False

    # Проверяем обязательные поля
    required_fields = ['symbol']

    for field in required_fields:
        if field not in data:
            return False

    # Проверяем символ
    if 'symbol' in data and not is_valid_crypto_symbol(data['symbol']):
        return False

    # Проверяем цену если есть
    if 'price' in data and not is_valid_amount(data['price'], min_value=0):
        return False

    # Проверяем объем если есть
    if 'volume' in data and not is_valid_amount(data['volume'], min_value=0):
        return False

    # Проверяем изменение цены если есть
    if 'change_24h' in data and not is_valid_percentage(data['change_24h']):
        return False

    return True
