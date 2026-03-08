# Execution/orders.py
from __future__ import annotations

"""Order helpers (Alpaca-first, test-friendly).

Design goals (your Feb-2026 requirements):
1) UI manual buy/sell/cancel works and Alpaca accepts the requests.
2) Public API is stable across refactors (engine/ui/tests should not break).
3) Every attempt is logged to CSV (trade_attempts.csv + order_events.csv) so you can audit.

Important Alpaca constraint:
 - Bracket orders require *whole share qty* (no fractional). If dollars implies < 1 share,
   we optionally fall back to a SIMPLE notional market order (fractional allowed).
"""

import math
from dataclasses import dataclass
from typing import Any, Optional

from qlib_tradingbot.config import DRY_RUN
from qlib_tradingbot.Data.logs import log_trade_attempt, log_order_event
from qlib_tradingbot.Execution.order_adapter import build_market_order_payload, should_use_alpaca_models


# Alpaca imports are lazy so dry-run/test paths never require alpaca-py.
ALPACA_AVAILABLE = False
OrderSide = TimeInForce = OrderClass = object  # type: ignore
MarketOrderRequest = TakeProfitRequest = StopLossRequest = GetOrdersRequest = object  # type: ignore


def _import_alpaca() -> None:
    global ALPACA_AVAILABLE, OrderSide, TimeInForce, OrderClass
    global MarketOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest

    if ALPACA_AVAILABLE:
        return

    from alpaca.trading.enums import OrderSide as _OrderSide, TimeInForce as _TimeInForce, OrderClass as _OrderClass
    from alpaca.trading.requests import (
        MarketOrderRequest as _MarketOrderRequest,
        TakeProfitRequest as _TakeProfitRequest,
        StopLossRequest as _StopLossRequest,
        GetOrdersRequest as _GetOrdersRequest,
    )

    OrderSide = _OrderSide
    TimeInForce = _TimeInForce
    OrderClass = _OrderClass
    MarketOrderRequest = _MarketOrderRequest
    TakeProfitRequest = _TakeProfitRequest
    StopLossRequest = _StopLossRequest
    GetOrdersRequest = _GetOrdersRequest
    ALPACA_AVAILABLE = True


STOP_LOSS_PCT = 0.0030
TAKE_PROFIT_PCT = 0.0060


@dataclass(frozen=True)
class OrderResult:
    ok: bool
    symbol: str
    action: str
    submitted: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    correlation_id: Optional[str] = None


__all__ = [
    "OrderResult",
    "place_advanced_order",
    "place_bracket_buy",
    "place_bracket_short",
    "place_simple_buy",
    "place_market_sell",
    "place_simple_sell",
    "cancel_order_by_id",
    "cancel_open_orders_for_symbol",
    "cancel_all_open_orders",
]


def _to_jsonable(x: Any) -> Any:
    """Best-effort conversion for logging."""
    if x is None:
        return None
    if isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, dict):
        return {k: _to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(v) for v in x]
    # alpaca-py models often expose model_dump
    if hasattr(x, "model_dump"):
        try:
            return _to_jsonable(x.model_dump())
        except Exception:
            pass
    if hasattr(x, "dict"):
        try:
            return _to_jsonable(x.dict())
        except Exception:
            pass
    return repr(x)


def _require_positive(x: Optional[float], name: str) -> None:
    if x is None or float(x) <= 0:
        raise ValueError(f"{name} must be > 0. Got {x!r}")


def _qty_from_dollars_floor(dollars: float, price: float) -> int:
    _require_positive(dollars, "dollars")
    _require_positive(price, "anchor_price")
    return int(math.floor(float(dollars) / float(price)))


def _safe_order_id(order_obj: Any) -> Optional[str]:
    for key in ("id", "order_id"):
        if hasattr(order_obj, key):
            try:
                v = getattr(order_obj, key)
                return str(v) if v else None
            except Exception:
                pass
        if isinstance(order_obj, dict) and key in order_obj:
            v = order_obj.get(key)
            return str(v) if v else None
    return None


def _submit(trading_client: Any, order_req: Any) -> Any:
    """Submit order_req if not DRY_RUN. Compatible with alpaca-py + unit-test fakes."""
    if DRY_RUN:
        return {"dry_run": True, "order_req": order_req}
    if hasattr(trading_client, "submit_order"):
        return trading_client.submit_order(order_req)
    return {"built": order_req}


def _build_market_order_request(
    trading_client: Any,
    *,
    symbol: str,
    side: str,
    time_in_force: str,
    qty: Optional[float] = None,
    notional: Optional[float] = None,
    client_order_id: Optional[str] = None,
) -> Any:
    if should_use_alpaca_models(trading_client):
        try:
            _import_alpaca()
        except Exception as e:
            raise RuntimeError("alpaca-py is required for alpaca client order submission") from e
        tif = TimeInForce.DAY if str(time_in_force).lower() == "day" else TimeInForce.GTC
        kwargs: dict[str, Any] = {
            "symbol": symbol,
            "side": OrderSide.BUY if str(side).upper() == "BUY" else OrderSide.SELL,
            "time_in_force": tif,
            "client_order_id": client_order_id,
        }
        if qty is not None:
            kwargs["qty"] = float(qty)
        if notional is not None:
            kwargs["notional"] = float(notional)
        return MarketOrderRequest(**kwargs)
    return build_market_order_payload(
        symbol=symbol,
        side=side,
        time_in_force=time_in_force,
        qty=qty,
        notional=notional,
        client_order_id=client_order_id,
    )


def place_bracket_buy(
    trading_client: Any,
    *,
    symbol: str,
    dollars: float,
    # Compatibility: older code passes last_close; v8 UI/engine pass anchor_price.
    anchor_price: Optional[float] = None,
    last_close: Optional[float] = None,
    score: Optional[float] = None,
    reasons: Optional[str] = None,
    run_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    strategy_id: Optional[str] = None,
    strategy_version: Optional[str] = None,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    time_in_force: str = "day",
    client_order_id: Optional[str] = None,
    allow_fractional_simple_fallback: bool = True,
) -> OrderResult:
    """Submit a MARKET BUY with BRACKET legs.

    Returns OrderResult and logs attempt + broker response.
    """

    action = "BRACKET_BUY"
    sym = symbol.upper().strip()
    side = "buy"

    price_basis = anchor_price if anchor_price is not None else last_close
    sl = STOP_LOSS_PCT if stop_loss_pct is None else float(stop_loss_pct)
    tp = TAKE_PROFIT_PCT if take_profit_pct is None else float(take_profit_pct)

    try:
        _require_positive(dollars, "dollars")
        _require_positive(price_basis, "anchor_price")

        qty_int = _qty_from_dollars_floor(float(dollars), float(price_basis))

        # If < 1 share, bracket cannot be used. Optionally fall back.
        if qty_int < 1:
            if not allow_fractional_simple_fallback:
                err = (
                    f"SKIPPED: Bracket requires whole-share qty. "
                    f"${float(dollars):.2f} at ~{float(price_basis):.2f} yields <1 share."
                )

                # Log as a SKIP (not an error) so daily reporting can distinguish it.
                log_trade_attempt(
                    symbol=sym,
                    side=side,
                    qty=None,
                    price=float(price_basis),
                    order_type="market_bracket",
                    tif=time_in_force,
                    strategy=strategy_id or "",
                    reason=reasons or "",
                    status="skipped",
                    error=err,
                    run_id=run_id or "",
                    correlation_id=correlation_id or "",
                    action="SKIPPED_BRACKET_INSUFFICIENT_DOLLARS",
                    dollars=float(dollars),
                    score=score,
                    strategy_version=strategy_version,
                )
                log_order_event(
                    symbol=sym,
                    event="skipped",
                    order_id="",
                    client_order_id=client_order_id,
                    side=side,
                    qty="",
                    run_id=run_id or "",
                    correlation_id=correlation_id or "",
                    strategy_id=strategy_id or "",
                    strategy_version=strategy_version or "",
                    notes="insufficient_dollars_for_bracket",
                    error=err,
                )
                return OrderResult(
                    True,
                    sym,
                    "SKIPPED_BRACKET_INSUFFICIENT_DOLLARS",
                    False,
                    None,
                    err,
                    correlation_id,
                )

            if not DRY_RUN:
                try:
                    _import_alpaca()
                except Exception as e:
                    raise RuntimeError("alpaca-py is required for live submit. Install: pip install alpaca-py") from e

            order_req = MarketOrderRequest(
                symbol=sym,
                notional=float(dollars),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                client_order_id=client_order_id,
            )

            log_trade_attempt(
                symbol=sym,
                side=side,
                qty=None,
                price=float(price_basis),
                order_type="market",
                tif=time_in_force,
                strategy=strategy_id or "",
                reason=reasons or "",
                status="intent",
                run_id=run_id or "",
                correlation_id=correlation_id or "",
                action="SIMPLE_NOTIONAL_BUY_FALLBACK",
                dollars=float(dollars),
                score=score,
                strategy_version=strategy_version,
            )

            resp = _submit(trading_client, order_req)
            oid = _safe_order_id(resp)
            log_order_event(
                symbol=sym,
                event="submit_order",
                order_id=oid,
                client_order_id=client_order_id,
                side=side,
                qty="",
                run_id=run_id or "",
                correlation_id=correlation_id or "",
                strategy_id=strategy_id or "",
                strategy_version=strategy_version or "",
                notes="fallback_simple_notional",
            )
            return OrderResult(True, sym, "SIMPLE_NOTIONAL_BUY_FALLBACK", not DRY_RUN, oid, None, correlation_id)

        # Build bracket request
        stop_price = round(float(price_basis) * (1.0 - sl), 2)
        take_profit_price = round(float(price_basis) * (1.0 + tp), 2)

        if not DRY_RUN:
            try:
                _import_alpaca()
            except Exception as e:
                raise RuntimeError("alpaca-py is required for live submit. Install: pip install alpaca-py") from e

        order_req = MarketOrderRequest(
            symbol=sym,
            qty=qty_int,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=take_profit_price),
            stop_loss=StopLossRequest(stop_price=stop_price),
            client_order_id=client_order_id,
        )

        log_trade_attempt(
            symbol=sym,
            side=side,
            qty=float(qty_int),
            price=float(price_basis),
            order_type="market_bracket",
            tif=time_in_force,
            strategy=strategy_id or "",
            reason=reasons or "",
            status="intent",
            run_id=run_id or "",
            correlation_id=correlation_id or "",
            action=action,
            dollars=float(dollars),
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            score=score,
            strategy_version=strategy_version,
        )

        resp = _submit(trading_client, order_req)
        oid = _safe_order_id(resp)
        log_order_event(
            symbol=sym,
            event="submit_order",
            order_id=oid,
            client_order_id=client_order_id,
            side=side,
            qty=str(qty_int),
            run_id=run_id or "",
            correlation_id=correlation_id or "",
            strategy_id=strategy_id or "",
            strategy_version=strategy_version or "",
            stop_price=str(stop_price),
            take_profit_price=str(take_profit_price),
        )
        return OrderResult(True, sym, action, not DRY_RUN, oid, None, correlation_id)

    except Exception as e:
        err = str(e)
        log_trade_attempt(
            symbol=sym,
            side=side,
            qty=None,
            price=float(price_basis) if price_basis is not None else None,
            order_type="market_bracket",
            tif=time_in_force,
            strategy=strategy_id or "",
            reason=reasons or "",
            status="error",
            error=err,
            run_id=run_id or "",
            correlation_id=correlation_id or "",
            action=action,
            dollars=float(dollars) if dollars is not None else None,
            score=score,
            strategy_version=strategy_version,
        )
        log_order_event(
            symbol=sym,
            event="submit_order_error",
            side=side,
            run_id=run_id or "",
            correlation_id=correlation_id or "",
            strategy_id=strategy_id or "",
            strategy_version=strategy_version or "",
            error=err,
        )
        return OrderResult(False, sym, action, False, None, err, correlation_id)


def place_bracket_short(
    trading_client: Any,
    *,
    symbol: str,
    qty: float,
    anchor_price: float,
    score: Optional[float] = None,
    reasons: Optional[str] = None,
    run_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    strategy_id: Optional[str] = None,
    strategy_version: Optional[str] = None,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    time_in_force: str = "day",
    client_order_id: Optional[str] = None,
) -> OrderResult:
    """Submit a MARKET SELL to OPEN a SHORT position with BRACKET legs.

    IMPORTANT:
      - Bracket orders require whole-share qty.
      - This function is only used when the user explicitly opts-in to short selling.
    """

    action = "BRACKET_SHORT"
    sym = symbol.upper().strip()
    side = "sell_short"

    sl = STOP_LOSS_PCT if stop_loss_pct is None else float(stop_loss_pct)
    tp = TAKE_PROFIT_PCT if take_profit_pct is None else float(take_profit_pct)

    try:
        _require_positive(anchor_price, "anchor_price")
        _require_positive(qty, "qty")

        qty_int = int(math.floor(float(qty)))
        if qty_int < 1:
            raise ValueError("Bracket short requires whole-share qty >= 1")

        # For shorts:
        #  - take profit is BELOW entry
        #  - stop loss is ABOVE entry
        take_profit_price = round(float(anchor_price) * (1.0 - tp), 2)
        stop_price = round(float(anchor_price) * (1.0 + sl), 2)

        if not DRY_RUN:
            try:
                _import_alpaca()
            except Exception as e:
                raise RuntimeError("alpaca-py is required for live submit. Install: pip install alpaca-py") from e

        order_req = MarketOrderRequest(
            symbol=sym,
            qty=qty_int,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=take_profit_price),
            stop_loss=StopLossRequest(stop_price=stop_price),
            client_order_id=client_order_id,
        )

        log_trade_attempt(
            symbol=sym,
            side=side,
            qty=float(qty_int),
            price=float(anchor_price),
            order_type="market",
            tif=time_in_force,
            strategy=strategy_id or "",
            reason=reasons or "",
            status="intent",
            run_id=run_id or "",
            correlation_id=correlation_id or "",
            action=action,
            score=score,
            strategy_version=strategy_version,
            extra={
                "stop_loss_pct": sl,
                "take_profit_pct": tp,
                "stop_price": stop_price,
                "take_profit_price": take_profit_price,
            },
        )

        resp = _submit(trading_client, order_req)
        oid = _safe_order_id(resp)
        log_order_event(
            symbol=sym,
            event="submit_order",
            order_id=oid,
            client_order_id=client_order_id,
            side=side,
            qty=str(qty_int),
            run_id=run_id or "",
            correlation_id=correlation_id or "",
            strategy_id=strategy_id or "",
            strategy_version=strategy_version or "",
            notes="bracket_short",
        )
        return OrderResult(True, sym, action, not DRY_RUN, oid, None, correlation_id)
    except Exception as e:
        log_trade_attempt(
            symbol=sym,
            side=side,
            qty=float(qty) if qty is not None else None,
            price=float(anchor_price) if anchor_price is not None else None,
            order_type="market",
            tif=time_in_force,
            strategy=strategy_id or "",
            reason=reasons or "",
            status="error",
            error=f"{type(e).__name__}: {e}",
            run_id=run_id or "",
            correlation_id=correlation_id or "",
            action=action,
            score=score,
            strategy_version=strategy_version,
        )
        return OrderResult(False, sym, action, False, None, f"{type(e).__name__}: {e}", correlation_id)

def place_market_sell(
    trading_client: Any,
    *,
    symbol: str,
    qty: float,
    reasons: str = "",
    run_id: str = "",
    correlation_id: str = "",
    strategy_id: str = "",
    strategy_version: str = "",
    time_in_force: str = "day",
    client_order_id: Optional[str] = None,
) -> OrderResult:
    action = "MARKET_SELL"
    sym = symbol.upper().strip()
    side = "sell"
    try:
        _require_positive(qty, "qty")
        order_req = _build_market_order_request(
            trading_client,
            symbol=sym,
            side="SELL",
            qty=float(qty),
            time_in_force=time_in_force,
            client_order_id=client_order_id,
        )

        log_trade_attempt(
            symbol=sym,
            side=side,
            qty=float(qty),
            price=None,
            order_type="market",
            tif=time_in_force,
            strategy=strategy_id,
            reason=reasons,
            status="intent",
            run_id=run_id,
            correlation_id=correlation_id,
            action=action,
            strategy_version=strategy_version,
        )

        resp = _submit(trading_client, order_req)
        oid = _safe_order_id(resp)
        log_order_event(
            symbol=sym,
            event="submit_order",
            order_id=oid,
            client_order_id=client_order_id,
            side=side,
            qty=str(qty),
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )
        return OrderResult(True, sym, action, not DRY_RUN, oid, None, correlation_id)
    except Exception as e:
        err = str(e)
        log_trade_attempt(
            symbol=sym,
            side=side,
            qty=float(qty) if qty is not None else None,
            status="error",
            error=err,
            run_id=run_id,
            correlation_id=correlation_id,
            action=action,
            strategy=strategy_id,
            strategy_version=strategy_version,
        )
        log_order_event(
            symbol=sym,
            event="submit_order_error",
            side=side,
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            error=err,
        )
        return OrderResult(False, sym, action, False, None, err, correlation_id)


def _iter_open_orders(trading_client: Any):
    """Return iterable of open orders from either alpaca-py or test fakes."""
    if hasattr(trading_client, "get_orders"):
        try:
            try:
                _import_alpaca()
            except Exception:
                pass
            if ALPACA_AVAILABLE:
                return trading_client.get_orders(GetOrdersRequest(status="open"))
        except Exception:
            pass
        return trading_client.get_orders()
    return []


def cancel_open_orders_for_symbol(
    trading_client: Any,
    *,
    symbol: str,
    run_id: str = "",
    correlation_id: str = "",
    strategy_id: str = "",
    strategy_version: str = "",
) -> int:
    """Cancel open orders matching symbol. Returns count cancelled."""
    sym = symbol.upper().strip()
    cancelled = 0
    for o in _iter_open_orders(trading_client):
        try:
            osym = str(getattr(o, "symbol", "") or (o.get("symbol") if isinstance(o, dict) else "")).upper()
        except Exception:
            osym = ""
        if osym != sym:
            continue

        oid = _safe_order_id(o)
        if not oid:
            continue

        log_trade_attempt(
            symbol=sym,
            side="",
            status="intent",
            action="CANCEL_ORDER",
            order_id=oid,
            run_id=run_id,
            correlation_id=correlation_id,
            strategy=strategy_id,
            strategy_version=strategy_version,
        )

        if not DRY_RUN and hasattr(trading_client, "cancel_order_by_id"):
            trading_client.cancel_order_by_id(oid)
        cancelled += 1

        log_order_event(
            symbol=sym,
            event="cancel_order",
            order_id=oid,
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )

    return cancelled


def cancel_all_open_orders(
    trading_client: Any,
    *,
    run_id: str = "",
    correlation_id: str = "",
    strategy_id: str = "",
    strategy_version: str = "",
) -> None:
    log_trade_attempt(
        symbol="*",
        side="",
        status="intent",
        action="CANCEL_ALL_ORDERS",
        run_id=run_id,
        correlation_id=correlation_id,
        strategy=strategy_id,
        strategy_version=strategy_version,
    )
    if not DRY_RUN and hasattr(trading_client, "cancel_orders"):
        trading_client.cancel_orders()
    log_order_event(
        symbol="*",
        event="cancel_all_orders",
        run_id=run_id,
        correlation_id=correlation_id,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
    )


def place_simple_buy(
    trading_client: Any,
    *,
    symbol: str,
    qty: float | None = None,
    dollars: float | None = None,
    allow_fractional: bool = True,
    time_in_force: str = "day",
    reasons: str = "simple_buy",
    run_id: str = "",
    correlation_id: str = "",
    strategy_id: str = "manual",
    strategy_version: str = "v1",
    client_order_id: Optional[str] = None,
) -> OrderResult:
    """Simple market BUY.

    - If qty is provided, buys qty.
    - Else if dollars is provided, buys notional (fractional supported).
    """
    symbol = str(symbol).upper().strip()
    if not symbol:
        raise ValueError("symbol is required")
    if qty is None and dollars is None:
        raise ValueError("Provide qty or dollars")

    
    if DRY_RUN:
        # Keep offline dry-run deterministic and dependency-free.
        res = OrderResult(ok=True, symbol=symbol, action=reasons, submitted=False, order_id=None, correlation_id=correlation_id)
        log_order_event(
            event="dry_run_no_alpaca",
            symbol=symbol,
            action=reasons,
            order_id="",
            status="DRY_RUN",
            extra={"note": "dry-run mode; skipping submit"},
            run_id=run_id or "",
            correlation_id=correlation_id or "",
            strategy_id=strategy_id or "",
            strategy_version=strategy_version or "",
        )
        return res
    if qty is not None:
        q = float(qty)
        _require_positive(q, "qty")
        req = _build_market_order_request(
            trading_client,
            symbol=symbol,
            side="BUY",
            qty=q,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
        )
    else:
        n = float(dollars)
        _require_positive(n, "dollars")
        if not allow_fractional:
            raise ValueError("Fractional disabled: provide qty instead of dollars")
        req = _build_market_order_request(
            trading_client,
            symbol=symbol,
            side="BUY",
            notional=n,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
        )

    log_trade_attempt(
        symbol=symbol,
        side="buy",
        status="intent",
        action="SIMPLE_BUY",
        run_id=run_id,
        correlation_id=correlation_id,
        strategy=strategy_id,
        strategy_version=strategy_version,
        score=None,
        reasons=reasons,
        extra={"qty": qty, "dollars": dollars, "allow_fractional": allow_fractional},
    )

    try:
        resp = _submit(trading_client, req)
        oid = _safe_order_id(resp)
        log_order_event(
            symbol=symbol,
            event="submit_simple_buy",
            order_id=oid,
            request_payload=_to_jsonable(req),
            response_payload=_to_jsonable(resp),
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )
        return OrderResult(
            ok=True,
            symbol=symbol,
            action="SIMPLE_BUY",
            submitted=not DRY_RUN,
            order_id=oid,
            correlation_id=correlation_id,
        )
    except Exception as e:
        log_order_event(
            symbol=symbol,
            event="submit_simple_buy_error",
            request_payload=_to_jsonable(req),
            response_payload={"error": str(e)},
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )
        return OrderResult(
            ok=False,
            symbol=symbol,
            action="SIMPLE_BUY",
            submitted=False,
            error=str(e),
            correlation_id=correlation_id,
        )


def place_simple_sell(
    trading_client: Any,
    *,
    symbol: str,
    qty: float,
    time_in_force: str = "day",
    reasons: str = "simple_sell",
    run_id: str = "",
    correlation_id: str = "",
    strategy_id: str = "manual",
    strategy_version: str = "v1",
    client_order_id: Optional[str] = None,
) -> OrderResult:
    """Simple market SELL."""
    symbol = str(symbol).upper().strip()
    if not symbol:
        raise ValueError("symbol is required")
    q = float(qty)
    _require_positive(q, "qty")
    
    if DRY_RUN:
        # Keep offline dry-run deterministic and dependency-free.
        res = OrderResult(ok=True, symbol=symbol, action=reasons, submitted=False, order_id=None, correlation_id=correlation_id)
        log_order_event(
            event="dry_run_no_alpaca",
            symbol=symbol,
            action=reasons,
            order_id="",
            status="DRY_RUN",
            extra={"note": "dry-run mode; skipping submit"},
            run_id=run_id or "",
            correlation_id=correlation_id or "",
            strategy_id=strategy_id or "",
            strategy_version=strategy_version or "",
        )
        return res
    req = _build_market_order_request(
        trading_client,
        symbol=symbol,
        side="SELL",
        qty=q,
        time_in_force=time_in_force,
        client_order_id=client_order_id,
    )

    log_trade_attempt(
        symbol=symbol,
        side="sell",
        status="intent",
        action="SIMPLE_SELL",
        run_id=run_id,
        correlation_id=correlation_id,
        strategy=strategy_id,
        strategy_version=strategy_version,
        score=None,
        reasons=reasons,
        extra={"qty": qty},
    )

    try:
        resp = _submit(trading_client, req)
        oid = _safe_order_id(resp)
        log_order_event(
            symbol=symbol,
            event="submit_simple_sell",
            order_id=oid,
            request_payload=_to_jsonable(req),
            response_payload=_to_jsonable(resp),
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )
        return OrderResult(
            ok=True,
            symbol=symbol,
            action="SIMPLE_SELL",
            submitted=not DRY_RUN,
            order_id=oid,
            correlation_id=correlation_id,
        )
    except Exception as e:
        log_order_event(
            symbol=symbol,
            event="submit_simple_sell_error",
            request_payload=_to_jsonable(req),
            response_payload={"error": str(e)},
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )
        return OrderResult(
            ok=False,
            symbol=symbol,
            action="SIMPLE_SELL",
            submitted=False,
            error=str(e),
            correlation_id=correlation_id,
        )


def place_advanced_order(
    trading_client: Any,
    *,
    symbol: str,
    side: str,
    order_type: str,
    qty: float | None = None,
    limit_price: float | None = None,
    stop_price: float | None = None,
    trail_percent: float | None = None,
    time_in_force: str = "day",
    run_id: str = "",
    correlation_id: str = "",
    strategy_id: str = "strategy",
    strategy_version: str = "v1",
) -> OrderResult:
    """Submit deterministic dict payload for advanced order types.

    This keeps paper/offline paths testable without requiring alpaca models.
    """
    sym = str(symbol).upper().strip()
    ot = str(order_type).upper().strip()
    sd = str(side).upper().strip()
    if not sym:
        return OrderResult(ok=False, symbol=sym, action=ot, submitted=False, error="symbol is required", correlation_id=correlation_id)
    if sd not in {"BUY", "SELL"}:
        return OrderResult(ok=False, symbol=sym, action=ot, submitted=False, error="side must be BUY or SELL", correlation_id=correlation_id)
    if qty is None or float(qty) <= 0:
        return OrderResult(ok=False, symbol=sym, action=ot, submitted=False, error="qty must be > 0", correlation_id=correlation_id)

    req = {
        "symbol": sym,
        "side": sd,
        "order_type": ot,
        "qty": float(qty),
        "time_in_force": str(time_in_force).lower(),
        "limit_price": None if limit_price is None else float(limit_price),
        "stop_price": None if stop_price is None else float(stop_price),
        "trail_percent": None if trail_percent is None else float(trail_percent),
    }
    log_trade_attempt(
        symbol=sym,
        side=sd.lower(),
        qty=float(qty),
        order_type=ot.lower(),
        tif=str(time_in_force).lower(),
        strategy=strategy_id,
        status="intent",
        run_id=run_id,
        correlation_id=correlation_id,
        strategy_version=strategy_version,
        extra={"payload": req},
    )
    try:
        resp = _submit(trading_client, req)
        oid = _safe_order_id(resp)
        log_order_event(
            symbol=sym,
            event="submit_advanced_order",
            order_id=oid,
            side=sd.lower(),
            qty=str(qty),
            type=ot.lower(),
            time_in_force=str(time_in_force).lower(),
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            request_payload=_to_jsonable(req),
            response_payload=_to_jsonable(resp),
        )
        return OrderResult(ok=True, symbol=sym, action=ot, submitted=not DRY_RUN, order_id=oid, correlation_id=correlation_id)
    except Exception as e:
        return OrderResult(ok=False, symbol=sym, action=ot, submitted=False, error=str(e), correlation_id=correlation_id)


def cancel_order_by_id(
    trading_client: Any,
    *,
    order_id: str,
    run_id: str = "",
    correlation_id: str = "",
    strategy_id: str = "manual",
    strategy_version: str = "v1",
) -> None:
    """Cancel a single order by order_id."""
    oid = str(order_id).strip()
    if not oid:
        raise ValueError("order_id is required")

    log_trade_attempt(
        symbol="",
        side="",
        status="intent",
        action="CANCEL_ORDER",
        run_id=run_id,
        correlation_id=correlation_id,
        strategy=strategy_id,
        strategy_version=strategy_version,
        extra={"order_id": oid},
    )

    if DRY_RUN:
        log_order_event(
            symbol="",
            event="cancel_order_dry_run",
            order_id=oid,
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )
        return

    try:
        if hasattr(trading_client, "cancel_order_by_id"):
            resp = trading_client.cancel_order_by_id(oid)
        else:
            resp = None
        log_order_event(
            symbol="",
            event="cancel_order",
            order_id=oid,
            response_payload=_to_jsonable(resp),
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )
    except Exception as e:
        log_order_event(
            symbol="",
            event="cancel_order_error",
            order_id=oid,
            response_payload={"error": str(e)},
            run_id=run_id,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )
        raise
