# Core/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

Side = Literal["BUY", "SELL"]
Timeframe = Literal["1Min", "5Min", "15Min", "1Day", "1Week"]


@dataclass(frozen=True)
class Signal:
    """A strategy output: what to trade and why."""
    symbol: str
    side: Side
    strategy_id: str
    strategy_version: str
    timeframe: Timeframe

    score: float = 0.0
    reasons: str = ""
    signal_ts_utc: str = ""          # ISO string when signal formed
    price_basis: float = 0.0         # last/close/trigger used at decision time

    run_id: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderIntent:
    """Execution instruction derived from a Signal (sizing + bracket parameters)."""
    symbol: str
    side: Side
    order_type: str                   # e.g. "BRACKET_MARKET"
    dollars: Optional[float] = None
    qty: Optional[float] = None

    # Bracket components (optional; can be computed from price_basis)
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None

    # Attribution / audit
    run_id: str = ""
    correlation_id: str = ""
    strategy_id: str = ""
    strategy_version: str = ""
    score: float = 0.0
    reasons: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)
