from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Execution.orders import OrderResult
from qlib_tradingbot.config import DEFAULT_STOP_LOSS_PCT, MAX_DOLLARS_PER_TRADE


def apply_signal_risk_controls(
    signals: Iterable[Signal],
    *,
    max_dollars_per_trade: float = MAX_DOLLARS_PER_TRADE,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
) -> tuple[list[Signal], list[OrderResult]]:
    """Size signals and enforce stop-loss prerequisites before execution."""
    accepted: list[Signal] = []
    rejected: list[OrderResult] = []

    max_dollars = float(max_dollars_per_trade)
    sl_pct = float(stop_loss_pct)
    for sig in signals:
        pb = float(sig.price_basis or 0.0)
        features = dict(sig.features or {})
        dollars = float(features.get("dollars", max_dollars) or 0.0)

        if dollars <= 0:
            rejected.append(
                OrderResult(
                    ok=False,
                    symbol=sig.symbol,
                    action="RISK_REJECT",
                    submitted=False,
                    error="invalid_dollars",
                    correlation_id=sig.correlation_id,
                )
            )
            continue

        if pb <= 0:
            rejected.append(
                OrderResult(
                    ok=False,
                    symbol=sig.symbol,
                    action="RISK_REJECT",
                    submitted=False,
                    error="missing_price_basis_for_stop_loss",
                    correlation_id=sig.correlation_id,
                )
            )
            continue

        sized = min(dollars, max_dollars)
        features["dollars"] = float(sized)
        features["risk_stop_price"] = round(pb * (1.0 - sl_pct), 4)
        accepted.append(replace(sig, features=features))

    return accepted, rejected
