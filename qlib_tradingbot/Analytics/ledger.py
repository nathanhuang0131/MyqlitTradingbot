from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

LEDGER_COLUMNS = [
    "timestamp",
    "strategy",
    "symbol",
    "side",
    "qty",
    "fill_price",
    "order_id",
    "event",
    "realized_pnl",
    "fees",
    "tags",
]


def _ensure_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(columns=LEDGER_COLUMNS).to_csv(path, index=False)
        return
    try:
        df = pd.read_csv(path)
    except Exception:
        df = pd.DataFrame(columns=LEDGER_COLUMNS)
    for col in LEDGER_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[LEDGER_COLUMNS]
    df.to_csv(path, index=False)


def append_execution_results_ledger(
    data_dir: str | Path,
    *,
    strategy: str,
    execution_result: list[Any],
    now_utc: datetime,
) -> Path:
    path = Path(data_dir) / "trades_ledger.csv"
    _ensure_ledger(path)

    rows: list[dict[str, Any]] = []
    for item in execution_result or []:
        payload = asdict(item) if hasattr(item, "__dataclass_fields__") else dict(item) if isinstance(item, dict) else {}
        side = str(payload.get("action", "")).upper()
        # Best-available mapping from execution outcomes.
        event = "OPEN" if side in {"BUY", "BRACKET_BUY", "BRACKET_MARKET", "BRACKET_SHORT", "SELL_SHORT"} else "CLOSE"
        rows.append(
            {
                "timestamp": now_utc.isoformat(),
                "strategy": strategy,
                "symbol": str(payload.get("symbol", "")),
                "side": side,
                "qty": payload.get("qty", ""),
                "fill_price": payload.get("fill_price", ""),
                "order_id": payload.get("order_id", ""),
                "event": event,
                "realized_pnl": payload.get("realized_pnl", ""),
                "fees": payload.get("fees", ""),
                "tags": payload.get("error", "") or payload.get("status", ""),
            }
        )

    if rows:
        out = pd.DataFrame(rows)
        for col in LEDGER_COLUMNS:
            if col not in out.columns:
                out[col] = pd.NA
        out = out[LEDGER_COLUMNS]
        out.to_csv(path, mode="a", header=False, index=False)

    return path
