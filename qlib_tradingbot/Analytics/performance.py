from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = [
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


def load_trades(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(p)
    except Exception:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[REQUIRED_COLUMNS]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out.get("timestamp"), errors="coerce", utc=True)
    out["realized_pnl"] = pd.to_numeric(out.get("realized_pnl"), errors="coerce").fillna(0.0)
    out["fees"] = pd.to_numeric(out.get("fees"), errors="coerce").fillna(0.0)
    out["net_pnl"] = out["realized_pnl"] - out["fees"]
    return out


def daily_pnl(trades: pd.DataFrame) -> pd.DataFrame:
    df = _normalize(trades)
    if df.empty:
        return pd.DataFrame(columns=["day", "realized_pnl", "fees", "net_pnl", "trades"])
    df = df.dropna(subset=["timestamp"])
    df["day"] = df["timestamp"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    out = (
        df.groupby("day", as_index=False)
        .agg(realized_pnl=("realized_pnl", "sum"), fees=("fees", "sum"), net_pnl=("net_pnl", "sum"), trades=("symbol", "count"))
        .sort_values("day")
        .reset_index(drop=True)
    )
    return out


def win_rate(trades: pd.DataFrame) -> dict[str, Any]:
    df = _normalize(trades)
    closed = df[df.get("event", "").astype(str).str.upper() == "CLOSE"].copy()
    if closed.empty:
        return {
            "wins": 0,
            "losses": 0,
            "total": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
        }

    wins = closed[closed["net_pnl"] > 0]
    losses = closed[closed["net_pnl"] < 0]
    wins_count = int(len(wins))
    losses_count = int(len(losses))
    total = wins_count + losses_count
    avg_win = float(wins["net_pnl"].mean()) if wins_count else 0.0
    avg_loss = float(losses["net_pnl"].mean()) if losses_count else 0.0
    gross_profit = float(wins["net_pnl"].sum())
    gross_loss_abs = float(abs(losses["net_pnl"].sum()))
    profit_factor = gross_profit / gross_loss_abs if gross_loss_abs > 0 else 0.0
    return {
        "wins": wins_count,
        "losses": losses_count,
        "total": total,
        "win_rate": (wins_count / total) if total else 0.0,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
    }


def breakdown_by_symbol(trades: pd.DataFrame) -> pd.DataFrame:
    df = _normalize(trades)
    if df.empty:
        return pd.DataFrame(columns=["symbol", "trades", "realized_pnl", "fees", "net_pnl"])
    out = (
        df.groupby("symbol", as_index=False)
        .agg(trades=("symbol", "count"), realized_pnl=("realized_pnl", "sum"), fees=("fees", "sum"), net_pnl=("net_pnl", "sum"))
        .sort_values("net_pnl", ascending=False)
        .reset_index(drop=True)
    )
    return out


def breakdown_by_strategy(trades: pd.DataFrame) -> pd.DataFrame:
    df = _normalize(trades)
    if df.empty:
        return pd.DataFrame(columns=["strategy", "trades", "realized_pnl", "fees", "net_pnl"])
    out = (
        df.groupby("strategy", as_index=False)
        .agg(trades=("strategy", "count"), realized_pnl=("realized_pnl", "sum"), fees=("fees", "sum"), net_pnl=("net_pnl", "sum"))
        .sort_values("net_pnl", ascending=False)
        .reset_index(drop=True)
    )
    return out
