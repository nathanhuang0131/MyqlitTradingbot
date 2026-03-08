from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

import pandas as pd

from qlib_tradingbot.config import BAR_INTERVAL

try:  # pragma: no cover
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    ALPACA_DATA_AVAILABLE = True
except Exception:  # pragma: no cover
    StockBarsRequest = TimeFrame = object  # type: ignore
    ALPACA_DATA_AVAILABLE = False


@dataclass(frozen=True)
class BarsResult:
    df: pd.DataFrame
    start: datetime
    end: datetime
    timeframe: str


def _tf_from_str(tf: str):
    if not ALPACA_DATA_AVAILABLE:
        raise RuntimeError("alpaca-py is not installed; cannot fetch bars.")
    tf = tf.strip()
    # Supported common strings like: 1Min, 5Min, 15Min, 1Hour, 1Day
    if tf.endswith("Min"):
        n = int(tf[:-3])
        return TimeFrame.Minute * n
    if tf.endswith("Hour"):
        n = int(tf[:-4])
        return TimeFrame.Hour * n
    if tf.endswith("Day"):
        n = int(tf[:-3])
        return TimeFrame.Day * n
    raise ValueError(f"Unsupported BAR_INTERVAL={tf!r}")


def fetch_bars(
    data_client,
    symbols: Iterable[str],
    *,
    start: datetime,
    end: datetime,
    timeframe: str = BAR_INTERVAL,
    adjustment: str = "raw",
) -> BarsResult:
    """Fetch OHLCV bars from Alpaca and return a normalized DataFrame.

    Output DataFrame columns: open, high, low, close, volume, vwap, trade_count
    Index: DatetimeIndex (UTC) + 'symbol' column.

    Note: Alpaca returns timestamps in UTC. We'll keep UTC throughout.
    """
    syms = sorted({s.strip().upper() for s in symbols if s and s.strip()})
    if not syms:
        return BarsResult(df=pd.DataFrame(), start=start, end=end, timeframe=timeframe)

    tf = _tf_from_str(timeframe)
    req = StockBarsRequest(symbol_or_symbols=syms, timeframe=tf, start=start, end=end, adjustment=adjustment)
    bars = data_client.get_stock_bars(req).df  # multi-index [symbol, timestamp]
    if bars is None or len(bars) == 0:
        return BarsResult(df=pd.DataFrame(), start=start, end=end, timeframe=timeframe)

    # normalize
    df = bars.reset_index().rename(columns={"timestamp": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df = df.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    return BarsResult(df=df, start=start, end=end, timeframe=timeframe)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(days: int) -> datetime:
    return utc_now() - timedelta(days=days)
