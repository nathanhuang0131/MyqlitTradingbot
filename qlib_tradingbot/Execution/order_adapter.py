from __future__ import annotations

from typing import Any, Optional


def _is_alpaca_client(trading_client: Any) -> bool:
    module_name = getattr(type(trading_client), "__module__", "") or ""
    return module_name.startswith("alpaca.")


def should_use_alpaca_models(trading_client: Any) -> bool:
    return _is_alpaca_client(trading_client)


def build_market_order_payload(
    *,
    symbol: str,
    side: str,
    time_in_force: str,
    qty: Optional[float] = None,
    notional: Optional[float] = None,
    client_order_id: Optional[str] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": str(symbol).upper().strip(),
        "side": str(side).upper().strip(),
        "time_in_force": str(time_in_force).lower(),
    }
    if qty is not None:
        payload["qty"] = float(qty)
    if notional is not None:
        payload["notional"] = float(notional)
    if client_order_id:
        payload["client_order_id"] = str(client_order_id)
    return payload

