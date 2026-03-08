from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from qlib_tradingbot.core.models import Signal, OrderIntent
import qlib_tradingbot.Execution.orders as orders_module
from qlib_tradingbot.Execution.mock_broker import MockExecutionEngine
from qlib_tradingbot.Execution.orders import (
    OrderResult,
    place_advanced_order,
    place_bracket_buy,
    place_bracket_short,
    place_market_sell,
    place_simple_buy,
    place_simple_sell,
)
from qlib_tradingbot.config import (
    DRY_RUN,
    MAX_DOLLARS_PER_TRADE,
    MAX_POSITIONS,
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_TAKE_PROFIT_PCT,
)


@dataclass(frozen=True)
class EngineConfig:
    max_positions: int = MAX_POSITIONS
    dollars_per_trade: float = MAX_DOLLARS_PER_TRADE


def intent_from_signal(sig: Signal, *, dollars_per_trade: float) -> OrderIntent:
    """Translate a Signal into an OrderIntent.

    Policy:
    - BUY signals default to BRACKET_MARKET.
    - SELL signals default to MARKET_SELL (closing long) unless strategy marks it as SHORT.
    - Strategy can override by setting sig.features['intent_order_type'].
    """
    ot = str(sig.features.get("intent_order_type", "") or "").upper().strip()

    if not ot:
        ot = "BRACKET_MARKET" if sig.side == "BUY" else "MARKET_SELL"

    intent = OrderIntent(
        symbol=sig.symbol,
        side=sig.side,
        order_type=ot,
        dollars=float(sig.features.get("dollars", dollars_per_trade) or dollars_per_trade),
    )

    # Bracket parameters derived from price_basis when missing
    pb = float(sig.price_basis or 0.0)
    if pb > 0 and intent.order_type.startswith("BRACKET") and intent.stop_price is None and intent.take_profit_price is None:
        from dataclasses import replace

        intent = replace(
            intent,
            stop_price=round(pb * (1.0 - DEFAULT_STOP_LOSS_PCT), 4),
            take_profit_price=round(pb * (1.0 + DEFAULT_TAKE_PROFIT_PCT), 4),
        )

    return intent
def _positions_count(trade_client) -> int:
    try:
        return len(trade_client.get_all_positions())
    except Exception:
        return 0


def _already_holding(trade_client, symbol: str) -> bool:
    try:
        positions = trade_client.get_all_positions()
        return any(getattr(p, "symbol", "") == symbol for p in positions)
    except Exception:
        return False


def execute_intent(trade_client, intent: OrderIntent, *, correlation_id: Optional[str] = None) -> OrderResult:
    ot = intent.order_type.upper()

    # Convert explicit stop/tp prices to pct when possible (orders.py expects pct).
    anchor_price = None
    try:
        anchor_price = float(intent.meta.get("anchor_price")) if isinstance(intent.meta, dict) and intent.meta.get("anchor_price") else None
    except Exception:
        anchor_price = None

    if anchor_price is None and intent.stop_price is not None and intent.take_profit_price is not None:
        # infer anchor from the midpoint (best effort)
        anchor_price = (float(intent.stop_price) + float(intent.take_profit_price)) / 2.0

    stop_loss_pct = None
    take_profit_pct = None
    if anchor_price and anchor_price > 0:
        if intent.stop_price is not None:
            stop_loss_pct = max(0.0, (anchor_price - float(intent.stop_price)) / anchor_price)
        if intent.take_profit_price is not None:
            take_profit_pct = max(0.0, (float(intent.take_profit_price) - anchor_price) / anchor_price)

    if ot in ("BRACKET_MARKET", "BRACKET_BUY"):
        return place_bracket_buy(
            trade_client,
            symbol=intent.symbol,
            dollars=float(intent.dollars or 0),
            anchor_price=anchor_price,
            correlation_id=correlation_id,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )
    if ot in ("BRACKET_SHORT", "BRACKET_SELL_SHORT"):
        return place_bracket_short(
            trade_client,
            symbol=intent.symbol,
            dollars=float(intent.dollars or 0),
            anchor_price=anchor_price,
            correlation_id=correlation_id,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )
    if ot in ("SIMPLE_BUY", "MARKET_BUY"):
        if intent.qty is not None:
            return place_simple_buy(trade_client, symbol=intent.symbol, qty=float(intent.qty), correlation_id=correlation_id)
        return place_simple_buy(trade_client, symbol=intent.symbol, dollars=float(intent.dollars or 0), correlation_id=correlation_id)
    if ot in ("SIMPLE_SELL", "MARKET_SELL"):
        if intent.qty is not None:
            return place_simple_sell(trade_client, symbol=intent.symbol, qty=float(intent.qty), correlation_id=correlation_id)

        # Best-effort: close existing long position if any
        qty = None
        try:
            if hasattr(trade_client, "get_position"):
                p = trade_client.get_position(intent.symbol)
                qty = float(getattr(p, "qty", None) or getattr(p, "quantity", None) or 0)
        except Exception:
            qty = None
        if qty is None or qty <= 0:
            try:
                for p in trade_client.get_all_positions():
                    if getattr(p, "symbol", "").upper() == intent.symbol.upper():
                        qty = float(getattr(p, "qty", None) or getattr(p, "quantity", None) or 0)
                        break
            except Exception:
                qty = None

        if qty is None or qty <= 0:
            return OrderResult(ok=False, symbol=intent.symbol, action=ot, submitted=False, error="SELL requires qty or an existing position", correlation_id=correlation_id)

        return place_simple_sell(trade_client, symbol=intent.symbol, qty=float(qty), correlation_id=correlation_id)

    if ot in ("LIMIT_BUY", "LIMIT_SELL", "STOP_BUY", "STOP_SELL", "STOP_LIMIT_BUY", "STOP_LIMIT_SELL", "TRAILING_STOP_BUY", "TRAILING_STOP_SELL"):
        side = "BUY" if ot.endswith("BUY") else "SELL"
        meta = intent.meta or {}
        qty = float(intent.qty or meta.get("qty", 0) or 0)
        limit_price = meta.get("limit_price")
        stop_px = intent.stop_price if intent.stop_price is not None else meta.get("stop_price")
        trail_percent = meta.get("trail_percent")
        return place_advanced_order(
            trade_client,
            symbol=intent.symbol,
            side=side,
            order_type=ot,
            qty=qty,
            limit_price=None if limit_price is None else float(limit_price),
            stop_price=None if stop_px is None else float(stop_px),
            trail_percent=None if trail_percent is None else float(trail_percent),
            correlation_id=correlation_id or "",
            strategy_id=intent.strategy_id or "strategy",
            strategy_version=intent.strategy_version or "v1",
        )

    return OrderResult(ok=False, symbol=intent.symbol, action=ot, submitted=False, error=f"Unknown order_type: {ot}", correlation_id=correlation_id)
def execute_signals(
    trade_client,
    signals: List[Signal],
    *,
    cfg: EngineConfig = EngineConfig(),
    allow_shorts: bool = True,
    dry_run: Optional[bool] = None,
    dry_run_output_dir: Optional[str | Path] = None,
) -> List[OrderResult]:
    """Execute signals with basic safety checks (position cap + already holding)."""
    is_dry_run = DRY_RUN if dry_run is None else bool(dry_run)
    mock_engine = MockExecutionEngine(output_dir=dry_run_output_dir) if is_dry_run else None

    results: List[OrderResult] = []
    original_orders_dry_run = bool(getattr(orders_module, "DRY_RUN", True))
    orders_module.DRY_RUN = is_dry_run
    try:
        for sig in signals:
            sym = sig.symbol.upper().strip()
            if not sym:
                continue

            if sig.side == "BUY":
                if _positions_count(trade_client) >= cfg.max_positions:
                    results.append(OrderResult(ok=False, symbol=sym, action="SKIP", submitted=False, error="max_positions reached", correlation_id=sig.correlation_id))
                    continue
                if _already_holding(trade_client, sym):
                    results.append(OrderResult(ok=True, symbol=sym, action="SKIP", submitted=False, error="already holding", correlation_id=sig.correlation_id))
                    continue

            intent = intent_from_signal(sig, dollars_per_trade=cfg.dollars_per_trade)
            if intent.order_type.upper() in ("BRACKET_SHORT", "BRACKET_SELL_SHORT") and not allow_shorts:
                results.append(
                    OrderResult(
                        ok=False,
                        symbol=sym,
                        action="SKIP",
                        submitted=False,
                        error="short selling disabled by safety preflight",
                        correlation_id=sig.correlation_id,
                    )
                )
                continue
            if mock_engine is not None:
                results.append(mock_engine.record(intent, correlation_id=sig.correlation_id))
                continue
            results.append(execute_intent(trade_client, intent, correlation_id=sig.correlation_id))
    finally:
        orders_module.DRY_RUN = original_orders_dry_run
    return results
