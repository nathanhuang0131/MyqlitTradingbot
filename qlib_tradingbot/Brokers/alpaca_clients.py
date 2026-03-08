from __future__ import annotations

from typing import Any, Optional

from qlib_tradingbot.bootstrap import settings as bootstrap_settings

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.trading.client import TradingClient

    ALPACA_AVAILABLE = True
except ModuleNotFoundError:
    StockHistoricalDataClient = TradingClient = object  # type: ignore
    ALPACA_AVAILABLE = False


class BrokerClientError(RuntimeError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def _mask_value(value: str) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def diagnose_broker_setup(*, paper: Optional[bool] = None, try_build: bool = True) -> dict[str, Any]:
    cfg = bootstrap_settings.get_settings()
    effective_paper = cfg.paper if paper is None else bool(paper)
    report: dict[str, Any] = {
        "env_file": str(cfg.env_file) if cfg.env_file else None,
        "mode": bootstrap_settings.current_mode(cfg),
        "broker_configured": bootstrap_settings.is_broker_configured(cfg),
        "alpaca_available": bool(ALPACA_AVAILABLE and bootstrap_settings.is_alpaca_available()),
        "keys": {
            "api_key": _mask_value(cfg.api_key),
            "api_secret": _mask_value(cfg.api_secret),
            "base_url": cfg.api_base_url or "<default>",
        },
        "client_build": {"ok": False, "error": None, "paper": effective_paper},
    }
    if not try_build:
        return report
    try:
        _dc, _tc = build_clients(paper=effective_paper)
        report["client_build"]["ok"] = True
    except Exception as exc:  # pragma: no cover - defensive reporting
        report["client_build"]["error"] = str(exc)
    return report


def _missing_config_message() -> str:
    diag = diagnose_broker_setup(try_build=False)
    env_file = diag.get("env_file") or "<not found>"
    return (
        "Broker client configuration is incomplete. "
        "Provide API credentials in environment variables or .env. "
        "Supported names: APCA_API_KEY_ID/APCA_API_SECRET_KEY or ALPACA_API_KEY/ALPACA_SECRET_KEY. "
        f"Detected .env: {env_file}."
    )


def build_clients(paper: bool = True):
    cfg = bootstrap_settings.get_settings(refresh=True)
    if not bootstrap_settings.is_broker_configured(cfg):
        raise BrokerClientError("broker_config_missing", _missing_config_message())
    if not ALPACA_AVAILABLE:
        raise BrokerClientError("alpaca_not_installed", "alpaca-py is not installed. Install: pip install alpaca-py")

    trade_kwargs: dict[str, Any] = {"api_key": cfg.api_key, "secret_key": cfg.api_secret, "paper": paper}
    if cfg.api_base_url:
        trade_kwargs["base_url"] = cfg.api_base_url

    data_client = StockHistoricalDataClient(api_key=cfg.api_key, secret_key=cfg.api_secret)
    try:
        trade_client = TradingClient(**trade_kwargs)
    except TypeError:
        trade_kwargs.pop("base_url", None)
        trade_client = TradingClient(**trade_kwargs)
    except Exception as exc:
        raise BrokerClientError("broker_client_build_failed", f"Unable to create Alpaca TradingClient: {exc}") from exc
    return data_client, trade_client
