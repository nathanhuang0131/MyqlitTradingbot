from __future__ import annotations

from typing import Any, Callable

from qlib_tradingbot.Brokers.alpaca_gateway import get_account


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "enabled"}


def account_supports_shorts(account: Any) -> bool:
    if account is None:
        return False

    shorting_enabled = getattr(account, "shorting_enabled", None)
    if shorting_enabled is not None:
        return _as_bool(shorting_enabled)

    multiplier = getattr(account, "multiplier", None)
    if multiplier is not None:
        try:
            return float(multiplier) > 1.0
        except Exception:
            pass

    account_type = str(getattr(account, "account_type", "") or "").strip().lower()
    if account_type in {"margin", "portfolio_margin"}:
        return True

    return False


def preflight_allow_shorts(
    trade_client: Any,
    requested_allow_shorts: bool,
    *,
    logger: Callable[[str], None] = print,
) -> bool:
    if not requested_allow_shorts:
        return False

    account = get_account(trade_client)
    if account_supports_shorts(account):
        return True

    logger("warning: short selling requested but account does not support margin/shorting; disabling allow_shorts")
    return False
