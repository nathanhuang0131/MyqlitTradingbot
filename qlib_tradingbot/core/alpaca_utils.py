from __future__ import annotations

"""qlib_tradingbot/Core/alpaca_utils.py

Compatibility helpers for Alpaca assets across alpaca-py versions.

Why this exists:
- alpaca-py has changed method names and request signatures across versions
- some fields may be Enums (with .value) or plain strings
- naive string comparisons can silently filter out all assets ("0 symbols" issue)
"""

from typing import Any, List, Optional


def _enum_to_str(v: Any) -> str:
    """Return a stable string representation for either Enum-like or plain values."""
    if v is None:
        return ""
    # Enum-like objects often expose `.value`
    try:
        vv = getattr(v, "value")
        if vv is not None:
            v = vv
    except Exception:
        pass
    return str(v)


def normalize_asset_class(v: Any) -> str:
    return _enum_to_str(v).strip().lower()


def normalize_exchange(v: Any) -> str:
    # Exchanges are generally codes (NASDAQ, NYSE, ARCA, OTC, ...)
    return _enum_to_str(v).strip().upper()


def fetch_alpaca_active_assets(trade_client, *, asset_class: Optional[str] = "us_equity") -> List[Any]:
    """Best-effort retrieval of active assets.

    Prefers modern request-object API, falls back to legacy signatures.
    `asset_class` is normalized to Alpaca's expected enum/value when possible.
    """
    # 1) Preferred: alpaca-py request objects
    try:
        from alpaca.trading.requests import GetAssetsRequest
        from alpaca.trading.enums import AssetStatus, AssetClass

        ac = None
        if asset_class:
            norm = normalize_asset_class(asset_class)
            if norm in ("us_equity", "us-equity", "usequity"):
                ac = AssetClass.US_EQUITY
            elif norm in ("crypto", "cryptocurrency"):
                ac = AssetClass.CRYPTO
            else:
                # best effort: try to pass through as string if enum doesn't exist
                ac = asset_class

        # Try with asset_class first (more selective, matches your Alpacatest style)
        try:
            req = GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=ac) if ac is not None else GetAssetsRequest(status=AssetStatus.ACTIVE)
            assets = trade_client.get_all_assets(req)
            return list(assets or [])
        except Exception:
            # fallback without asset_class
            req = GetAssetsRequest(status=AssetStatus.ACTIVE)
            assets = trade_client.get_all_assets(req)
            return list(assets or [])
    except Exception:
        pass

    # 2) Legacy keyword signatures
    try:
        assets = trade_client.get_all_assets(status="active")
        return list(assets or [])
    except Exception:
        pass

    try:
        assets = trade_client.get_assets(status="active")
        return list(assets or [])
    except Exception:
        return []
