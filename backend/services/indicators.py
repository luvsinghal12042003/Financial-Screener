from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


SUPPORTED_INDICATORS = [
    # Trend Overlays
    {
        "id": "SMA_20",
        "name": "SMA (20)",
        "category": "trend",
        "type": "overlay",
        "description": "20-period Simple Moving Average"
    },
    {
        "id": "SMA_50",
        "name": "SMA (50)",
        "category": "trend",
        "type": "overlay",
        "description": "50-period Simple Moving Average"
    },
    {
        "id": "SMA_100",
        "name": "SMA (100)",
        "category": "trend",
        "type": "overlay",
        "description": "100-period Simple Moving Average"
    },
    {
        "id": "SMA_200",
        "name": "SMA (200)",
        "category": "trend",
        "type": "overlay",
        "description": "200-period Simple Moving Average"
    },
    {
        "id": "EMA_20",
        "name": "EMA (20)",
        "category": "trend",
        "type": "overlay",
        "description": "20-period Exponential Moving Average"
    },
    {
        "id": "EMA_50",
        "name": "EMA (50)",
        "category": "trend",
        "type": "overlay",
        "description": "50-period Exponential Moving Average"
    },
    {
        "id": "EMA_200",
        "name": "EMA (200)",
        "category": "trend",
        "type": "overlay",
        "description": "200-period Exponential Moving Average"
    },
    # Volatility Overlays & Subplots
    {
        "id": "BB",
        "name": "Bollinger Bands (20, 2)",
        "category": "volatility",
        "type": "overlay",
        "description": "Bollinger Bands with 20 SMA and 2 Standard Deviations"
    },
    {
        "id": "ATR",
        "name": "ATR (14)",
        "category": "volatility",
        "type": "subplot",
        "description": "Average True Range (14-period)"
    },
    # Momentum Subplots
    {
        "id": "RSI",
        "name": "RSI (14)",
        "category": "momentum",
        "type": "subplot",
        "description": "Relative Strength Index (14-period)"
    },
    {
        "id": "MACD",
        "name": "MACD (12, 26, 9)",
        "category": "momentum",
        "type": "subplot",
        "description": "Moving Average Convergence Divergence"
    },
    {
        "id": "STOCH",
        "name": "Stochastic Oscillator (14, 3)",
        "category": "momentum",
        "type": "subplot",
        "description": "Stochastic Oscillator (%K 14, %D 3)"
    },
    # Volume
    {
        "id": "VOL_MA",
        "name": "Volume MA (20)",
        "category": "volume",
        "type": "volume_overlay",
        "description": "20-period Moving Average on Volume"
    }
]


def clean_series(series: pd.Series) -> List[Optional[float]]:
    """Converts a pandas Series to a list with NaN / Inf replaced by None and rounded."""
    cleaned = []
    for val in series:
        if pd.isna(val) or np.isinf(val):
            cleaned.append(None)
        else:
            cleaned.append(round(float(val), 2))
    return cleaned


def calculate_sma(df: pd.DataFrame, period: int) -> List[Optional[float]]:
    sma = df["Close"].rolling(window=period, min_periods=period).mean()
    return clean_series(sma)


def calculate_ema(df: pd.DataFrame, period: int) -> List[Optional[float]]:
    ema = df["Close"].ewm(span=period, adjust=False, min_periods=period).mean()
    return clean_series(ema)


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, num_std: float = 2.0) -> Dict[str, List[Optional[float]]]:
    middle = df["Close"].rolling(window=period, min_periods=period).mean()
    std = df["Close"].rolling(window=period, min_periods=period).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return {
        "middle": clean_series(middle),
        "upper": clean_series(upper),
        "lower": clean_series(lower)
    }


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> List[Optional[float]]:
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's smoothing technique
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Handle division by zero edge cases
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(avg_gain != 0, 0.0)
    return clean_series(rsi)


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal_period: int = 9) -> Dict[str, List[Optional[float]]]:
    ema_fast = df["Close"].ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
    histogram = macd_line - signal_line

    return {
        "macd": clean_series(macd_line),
        "signal": clean_series(signal_line),
        "histogram": clean_series(histogram)
    }


def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Dict[str, List[Optional[float]]]:
    low_min = df["Low"].rolling(window=k_period, min_periods=k_period).min()
    high_max = df["High"].rolling(window=k_period, min_periods=k_period).max()
    diff = high_max - low_min
    diff = diff.replace(0, np.nan)
    k = 100.0 * ((df["Close"] - low_min) / diff)
    d = k.rolling(window=d_period, min_periods=d_period).mean()

    return {
        "k": clean_series(k),
        "d": clean_series(d)
    }


def calculate_atr(df: pd.DataFrame, period: int = 14) -> List[Optional[float]]:
    prev_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return clean_series(atr)


def calculate_volume_ma(df: pd.DataFrame, period: int = 20) -> List[Optional[float]]:
    vol_ma = df["Volume"].rolling(window=period, min_periods=period).mean()
    return clean_series(vol_ma)


def compute_requested_indicators(df: pd.DataFrame, indicator_ids: List[str]) -> Dict[str, Any]:
    """
    Computes all indicators requested in indicator_ids on the given OHLCV DataFrame.
    Returns a dictionary keyed by indicator ID.
    """
    results: Dict[str, Any] = {}
    if df is None or len(df) == 0:
        return results

    # Normalize IDs
    ids = [i.strip().upper() for i in indicator_ids if i.strip()]

    for ind_id in ids:
        if ind_id == "SMA_20":
            results["SMA_20"] = calculate_sma(df, 20)
        elif ind_id == "SMA_50":
            results["SMA_50"] = calculate_sma(df, 50)
        elif ind_id == "SMA_100":
            results["SMA_100"] = calculate_sma(df, 100)
        elif ind_id == "SMA_200":
            results["SMA_200"] = calculate_sma(df, 200)
        elif ind_id == "EMA_20":
            results["EMA_20"] = calculate_ema(df, 20)
        elif ind_id == "EMA_50":
            results["EMA_50"] = calculate_ema(df, 50)
        elif ind_id == "EMA_200":
            results["EMA_200"] = calculate_ema(df, 200)
        elif ind_id in ("BB", "BOLLINGER_BANDS"):
            results["BB"] = calculate_bollinger_bands(df, 20, 2.0)
        elif ind_id == "RSI":
            results["RSI"] = calculate_rsi(df, 14)
        elif ind_id == "MACD":
            results["MACD"] = calculate_macd(df, 12, 26, 9)
        elif ind_id in ("STOCH", "STOCHASTIC"):
            results["STOCH"] = calculate_stochastic(df, 14, 3)
        elif ind_id == "ATR":
            results["ATR"] = calculate_atr(df, 14)
        elif ind_id in ("VOL_MA", "VOLUME_MA"):
            results["VOL_MA"] = calculate_volume_ma(df, 20)

    return results
