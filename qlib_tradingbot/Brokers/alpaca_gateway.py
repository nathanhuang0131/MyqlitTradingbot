from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def enum_value(x: Any) -> Any:
    try:
        return x.value
    except Exception:
        return x


def as_bool(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    s = str(enum_value(x)).strip().lower()
    return s in {"1", "true", "yes", "open"}


@dataclass(frozen=True)
class MarketClock:
    is_open: bool
    timestamp_utc: datetime
    next_open_utc: datetime | None
    next_close_utc: datetime | None


def get_market_clock(trade_client: Any) -> MarketClock:
    now_utc = datetime.now(timezone.utc)
    if trade_client is None or not hasattr(trade_client, "get_clock"):
        return MarketClock(False, now_utc, None, None)
    try:
        clk = trade_client.get_clock()
    except Exception:
        return MarketClock(False, now_utc, None, None)
    is_open = as_bool(getattr(clk, "is_open", False))
    next_open = getattr(clk, "next_open", None)
    next_close = getattr(clk, "next_close", None)
    return MarketClock(is_open=is_open, timestamp_utc=now_utc, next_open_utc=next_open, next_close_utc=next_close)


def get_positions(trade_client: Any) -> list[Any]:
    if trade_client is None:
        return []
    try:
        return list(trade_client.get_all_positions() or [])
    except Exception:
        return []


def get_orders(trade_client: Any) -> list[Any]:
    if trade_client is None:
        return []
    try:
        if hasattr(trade_client, "get_orders"):
            return list(trade_client.get_orders() or [])
    except Exception:
        return []
    return []


def get_account(trade_client: Any) -> Any:
    if trade_client is None:
        return None
    try:
        return trade_client.get_account()
    except Exception:
        return None
