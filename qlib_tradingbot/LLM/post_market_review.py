from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from qlib_tradingbot.Brokers.alpaca_gateway import get_positions
from qlib_tradingbot.LLM.prompt_builder import build_post_market_prompt, dated_filename


CSV_COLUMNS = [
    "timestamp",
    "row_type",
    "strategy_type",
    "symbol",
    "qty",
    "avg_entry",
    "current_price",
    "unrealized_pnl",
    "timeframe",
    "rsi14",
    "macd",
    "macd_signal",
    "ema9",
    "ema21",
    "atr14",
    "vwap",
    "volume_vs_avg",
    "notes",
]


def _timeframe_for_strategy(strategy_type: str) -> str:
    s = str(strategy_type).strip().lower()
    if s == "scalping":
        return "1m+5m"
    if s == "intraday":
        return "5m"
    if s == "short-term":
        return "30m"
    return "1h"


def _to_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def _rsi(close: pd.Series, period: int = 14) -> float:
    if close.empty or len(close) < period + 1:
        return float("nan")
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    v = 100 - (100 / (1 + rs))
    return float(v.iloc[-1]) if not pd.isna(v.iloc[-1]) else float("nan")


def _compute_indicators(bars: pd.DataFrame) -> dict[str, float]:
    if bars is None or bars.empty:
        return {k: float("nan") for k in ["rsi14", "macd", "macd_signal", "ema9", "ema21", "atr14", "vwap", "volume_vs_avg"]}

    close = _to_series(bars, "close").dropna()
    high = _to_series(bars, "high").dropna()
    low = _to_series(bars, "low").dropna()
    volume = _to_series(bars, "volume").dropna()

    if close.empty:
        return {k: float("nan") for k in ["rsi14", "macd", "macd_signal", "ema9", "ema21", "atr14", "vwap", "volume_vs_avg"]}

    ema9 = close.ewm(span=9, adjust=False).mean().iloc[-1]
    ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean().iloc[-1]

    atr14 = float("nan")
    if not high.empty and not low.empty and len(close) > 1:
        high = high.reindex(close.index, fill_value=pd.NA)
        low = low.reindex(close.index, fill_value=pd.NA)
        prev_close = close.shift(1)
        tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr14 = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else float("nan")

    vwap = float("nan")
    volume_vs_avg = float("nan")
    if not volume.empty and not high.empty and not low.empty:
        typical = (high + low + close) / 3.0
        denom = volume.cumsum().iloc[-1]
        if denom and denom > 0:
            vwap = float((typical * volume).cumsum().iloc[-1] / denom)
        avg_vol = float(volume.tail(20).mean()) if len(volume) else float("nan")
        last_vol = float(volume.iloc[-1]) if len(volume) else float("nan")
        if avg_vol and avg_vol > 0:
            volume_vs_avg = last_vol / avg_vol

    return {
        "rsi14": _rsi(close, 14),
        "macd": float(macd.iloc[-1]) if len(macd) else float("nan"),
        "macd_signal": float(macd_signal),
        "ema9": float(ema9),
        "ema21": float(ema21),
        "atr14": float(atr14),
        "vwap": float(vwap),
        "volume_vs_avg": float(volume_vs_avg),
    }


def _normalize_bars(obj: Any, symbol: str) -> pd.DataFrame:
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        out = obj.copy()
    elif hasattr(obj, "df") and isinstance(obj.df, pd.DataFrame):
        out = obj.df.copy()
    elif isinstance(obj, dict):
        if symbol in obj and isinstance(obj[symbol], pd.DataFrame):
            out = obj[symbol].copy()
        else:
            return pd.DataFrame()
    else:
        return pd.DataFrame()
    out.columns = [str(c).lower() for c in out.columns]
    return out


def _fetch_bars(data_client: Any, symbol: str, timeframe: str) -> pd.DataFrame:
    if data_client is None:
        return pd.DataFrame()
    candidates = [
        ("get_stock_bars", lambda m: m(symbol, timeframe=timeframe, limit=200)),
        ("get_bars", lambda m: m(symbol, timeframe=timeframe, limit=200)),
        ("fetch_bars", lambda m: m(symbol, timeframe=timeframe, limit=200)),
    ]
    for name, call in candidates:
        if hasattr(data_client, name):
            try:
                raw = call(getattr(data_client, name))
                return _normalize_bars(raw, symbol)
            except Exception:
                continue
    return pd.DataFrame()


def generate_post_market_package(
    *,
    data_dir: str | Path,
    trade_client: Any,
    data_client: Any,
    strategy_type: str,
    now_utc: datetime | None = None,
) -> tuple[Path, Path]:
    now = now_utc or datetime.now(timezone.utc)
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    timeframe = _timeframe_for_strategy(strategy_type)

    rows: list[dict[str, Any]] = []
    symbols: list[str] = []
    for p in get_positions(trade_client):
        sym = str(getattr(p, "symbol", "") or "").upper()
        if not sym:
            continue
        symbols.append(sym)
        bars = _fetch_bars(data_client, sym, timeframe)
        ind = _compute_indicators(bars)
        rows.append(
            {
                "timestamp": now.isoformat(),
                "row_type": "position",
                "strategy_type": strategy_type,
                "symbol": sym,
                "qty": getattr(p, "qty", ""),
                "avg_entry": getattr(p, "avg_entry_price", ""),
                "current_price": getattr(p, "current_price", ""),
                "unrealized_pnl": getattr(p, "unrealized_pl", ""),
                "timeframe": timeframe,
                **ind,
                "notes": "",
            }
        )

    spy_bars = _fetch_bars(data_client, "SPY", timeframe)
    spy_ind = _compute_indicators(spy_bars)
    rows.append(
        {
            "timestamp": now.isoformat(),
            "row_type": "market_context",
            "strategy_type": strategy_type,
            "symbol": "SPY",
            "qty": "",
            "avg_entry": "",
            "current_price": "",
            "unrealized_pnl": "",
            "timeframe": timeframe,
            **spy_ind,
            "notes": "SPY trend snapshot",
        }
    )

    upload_name = dated_filename("llm_upload", now, "csv")
    prompt_name = dated_filename("llm_prompt", now, "txt")
    upload_path = data_dir / upload_name
    prompt_path = data_dir / prompt_name

    out = pd.DataFrame(rows)
    for col in CSV_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    out = out[CSV_COLUMNS]
    out.to_csv(upload_path, index=False)

    prompt = build_post_market_prompt(
        as_of_date=now.strftime("%Y-%m-%d"),
        strategy_type=strategy_type,
        csv_filename=upload_name,
        symbols=symbols,
    )
    prompt_path.write_text(prompt, encoding="utf-8")
    return upload_path, prompt_path
