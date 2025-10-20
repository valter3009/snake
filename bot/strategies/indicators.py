"""
Технические индикаторы для торговых стратегий
"""

import pandas as pd
import numpy as np
from typing import Tuple


def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Расчет индикатора RSI (Relative Strength Index)

    Args:
        data: DataFrame с данными OHLCV
        period: Период для расчета RSI

    Returns:
        Series с значениями RSI
    """
    delta = data['close'].diff()

    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_ma(data: pd.DataFrame, period: int = 20, column: str = 'close') -> pd.Series:
    """
    Расчет простой скользящей средней (Simple Moving Average)

    Args:
        data: DataFrame с данными OHLCV
        period: Период для расчета MA
        column: Название колонки для расчета

    Returns:
        Series с значениями MA
    """
    return data[column].rolling(window=period).mean()


def calculate_ema(data: pd.DataFrame, period: int = 20, column: str = 'close') -> pd.Series:
    """
    Расчет экспоненциальной скользящей средней (Exponential Moving Average)

    Args:
        data: DataFrame с данными OHLCV
        period: Период для расчета EMA
        column: Название колонки для расчета

    Returns:
        Series с значениями EMA
    """
    return data[column].ewm(span=period, adjust=False).mean()


def calculate_macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Расчет индикатора MACD

    Args:
        data: DataFrame с данными OHLCV
        fast: Период быстрой EMA
        slow: Период медленной EMA
        signal: Период сигнальной линии

    Returns:
        Tuple (MACD, Signal line, Histogram)
    """
    ema_fast = calculate_ema(data, fast)
    ema_slow = calculate_ema(data, slow)

    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line

    return macd, signal_line, histogram


def calculate_bollinger_bands(data: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Расчет полос Боллинджера

    Args:
        data: DataFrame с данными OHLCV
        period: Период для расчета
        std_dev: Количество стандартных отклонений

    Returns:
        Tuple (Upper band, Middle band, Lower band)
    """
    middle_band = calculate_ma(data, period)
    std = data['close'].rolling(window=period).std()

    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)

    return upper_band, middle_band, lower_band


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Расчет Average True Range (ATR)

    Args:
        data: DataFrame с данными OHLCV
        period: Период для расчета

    Returns:
        Series с значениями ATR
    """
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()

    return atr


def calculate_stochastic(data: pd.DataFrame, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[pd.Series, pd.Series]:
    """
    Расчет стохастического осциллятора

    Args:
        data: DataFrame с данными OHLCV
        period: Период для расчета
        smooth_k: Период сглаживания %K
        smooth_d: Период сглаживания %D

    Returns:
        Tuple (%K, %D)
    """
    lowest_low = data['low'].rolling(window=period).min()
    highest_high = data['high'].rolling(window=period).max()

    k_percent = 100 * ((data['close'] - lowest_low) / (highest_high - lowest_low))
    k_percent = k_percent.rolling(window=smooth_k).mean()
    d_percent = k_percent.rolling(window=smooth_d).mean()

    return k_percent, d_percent


def calculate_volume_ma(data: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Расчет скользящей средней объема

    Args:
        data: DataFrame с данными OHLCV
        period: Период для расчета

    Returns:
        Series с значениями MA объема
    """
    return data['volume'].rolling(window=period).mean()


def add_all_indicators(data: pd.DataFrame, rsi_period: int = 14,
                       ma_short: int = 20, ma_long: int = 50) -> pd.DataFrame:
    """
    Добавление всех основных индикаторов к DataFrame

    Args:
        data: DataFrame с данными OHLCV
        rsi_period: Период для RSI
        ma_short: Период короткой MA
        ma_long: Период длинной MA

    Returns:
        DataFrame с добавленными индикаторами
    """
    df = data.copy()

    # RSI
    df['rsi'] = calculate_rsi(df, rsi_period)

    # Moving Averages
    df['ma_short'] = calculate_ma(df, ma_short)
    df['ma_long'] = calculate_ma(df, ma_long)

    # EMA
    df['ema_short'] = calculate_ema(df, ma_short)
    df['ema_long'] = calculate_ema(df, ma_long)

    # MACD
    df['macd'], df['macd_signal'], df['macd_histogram'] = calculate_macd(df)

    # Bollinger Bands
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = calculate_bollinger_bands(df)

    # ATR
    df['atr'] = calculate_atr(df)

    # Stochastic
    df['stoch_k'], df['stoch_d'] = calculate_stochastic(df)

    # Volume MA
    df['volume_ma'] = calculate_volume_ma(df)

    return df
