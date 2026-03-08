from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "ret_1",
    "ret_3",
    "ret_6",
    "ret_12",
    "gap_open",
    "intraday_return",
    "vol_ratio_1",
    "dollar_vol",
    "spread_proxy",
    "rvol_day",
    "vwap_dist",
    "bb_z",
    "rsi_14",
    "macd_hist",
    "trend_strength",
]

LABEL_COLUMN = "label_fwd_ret_6"


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.replace(0, np.nan)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = _safe_div(avg_gain, avg_loss)
    return (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)


def build_intraday_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Build deterministic intraday OHLCV features and forward label."""
    if ohlcv is None or ohlcv.empty:
        return pd.DataFrame(columns=[*FEATURE_COLUMNS, LABEL_COLUMN])

    df = ohlcv.copy()
    if "timestamp" not in df.columns and "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    df = df.sort_values("timestamp").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df.get(col, 0.0), errors="coerce").fillna(0.0)

    prev_close = df["close"].shift(1)
    df["ret_1"] = df["close"].pct_change(1)
    df["ret_3"] = df["close"].pct_change(3)
    df["ret_6"] = df["close"].pct_change(6)
    df["ret_12"] = df["close"].pct_change(12)
    df["gap_open"] = _safe_div(df["open"] - prev_close, prev_close)

    session_open = df["open"].iloc[0] if len(df) else 0.0
    df["intraday_return"] = (df["close"] / session_open - 1.0) if session_open else 0.0

    vol20 = df["volume"].rolling(20).mean()
    df["vol_ratio_1"] = _safe_div(df["volume"], vol20)
    df["dollar_vol"] = df["close"] * df["volume"]
    df["spread_proxy"] = _safe_div(df["high"] - df["low"], df["close"])

    # Relative volume vs same-day average proxy (OHLCV-only deterministic fallback)
    df["rvol_day"] = _safe_div(df["volume"], df["volume"].expanding().mean())

    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_tpv = (typical * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum().replace(0, np.nan)
    vwap = _safe_div(cum_tpv, cum_vol)
    df["vwap_dist"] = _safe_div(df["close"] - vwap, vwap)

    ma20 = df["close"].rolling(20).mean()
    sd20 = df["close"].rolling(20).std()
    df["bb_z"] = _safe_div(df["close"] - ma20, sd20)

    df["rsi_14"] = _rsi(df["close"], period=14)

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["macd_hist"] = macd - signal

    # OHLC-only trend strength fallback as rolling directional efficiency.
    abs_move = (df["close"] - df["close"].shift(14)).abs()
    path = df["close"].diff().abs().rolling(14).sum()
    df["trend_strength"] = _safe_div(abs_move, path)

    df[LABEL_COLUMN] = df["close"].shift(-6) / df["close"] - 1.0

    out = df[[*FEATURE_COLUMNS, LABEL_COLUMN]].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return out


__all__ = ["FEATURE_COLUMNS", "LABEL_COLUMN", "build_intraday_features"]
