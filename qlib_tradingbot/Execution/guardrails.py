from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from qlib_tradingbot.bootstrap.settings import is_broker_configured


@dataclass(frozen=True)
class GuardrailResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def _daily_loss_breached(data_dir: Path, daily_loss_limit: float) -> bool:
    pnl = data_dir / "performance" / "pnl_daily.csv"
    if not pnl.exists():
        return False
    try:
        df = pd.read_csv(pnl)
        if df.empty or "net_pnl" not in df.columns:
            return False
        val = float(pd.to_numeric(df["net_pnl"], errors="coerce").fillna(0.0).iloc[-1])
        return val <= float(daily_loss_limit)
    except Exception:
        return False


def _max_exposure_breached(trade_client: Any, max_positions: int) -> bool:
    try:
        positions = trade_client.get_all_positions() if trade_client is not None else []
        return len(list(positions or [])) >= int(max_positions)
    except Exception:
        return False


def evaluate_execution_guardrails(
    *,
    dry_run: bool,
    trade_client: Any,
    signals_count: int,
    data_dir: Path | str,
    cfg: dict[str, Any] | None = None,
) -> GuardrailResult:
    cfg = dict(cfg or {})
    reasons: list[str] = []
    details: dict[str, Any] = {"signals_count": int(signals_count)}
    root = Path(data_dir)
    if dry_run:
        return GuardrailResult(ok=True, reasons=[], details={"dry_run": True, **details})

    if not is_broker_configured() and not bool(cfg.get("broker_configured", False)):
        reasons.append("broker_not_configured")
    if trade_client is None:
        reasons.append("missing_trade_client")
    if trade_client is not None and not hasattr(trade_client, "submit_order"):
        reasons.append("trade_client_unhealthy_no_submit")

    daily_loss_limit = cfg.get("daily_loss_limit")
    if daily_loss_limit is not None and _daily_loss_breached(root, float(daily_loss_limit)):
        reasons.append("daily_loss_limit_breached")
    max_positions = int(cfg.get("max_positions", 999999))
    if max_positions < 999999 and _max_exposure_breached(trade_client, max_positions):
        reasons.append("max_exposure_breached")

    if signals_count <= 0:
        reasons.append("no_signals")

    details.update({"daily_loss_limit": daily_loss_limit, "max_positions": max_positions})
    return GuardrailResult(ok=not reasons, reasons=reasons, details=details)

