from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qlib_tradingbot.Utils.timezone_utils import NY_TZ, to_new_york

ORDERS_HEADERS = [
    "timestamp_ny",
    "strategy",
    "symbol",
    "side",
    "order_type",
    "qty",
    "dollars",
    "status",
    "order_id",
    "correlation_id",
]
SIGNALS_HEADERS = [
    "timestamp_ny",
    "strategy",
    "symbol",
    "side",
    "score",
    "reasons",
    "run_id",
    "correlation_id",
]
POSITIONS_HEADERS = [
    "timestamp_ny",
    "strategy",
    "symbol",
    "qty",
    "avg_entry_price",
    "market_value",
    "unrealized_pl",
]
PNL_DAILY_HEADERS = [
    "day_ny",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
]
WIN_RATE_HEADERS = ["period", "strategy", "wins", "losses", "win_rate"]


def ensure_schema(path: Path, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(columns=headers).to_csv(path, index=False)
        return
    try:
        df = pd.read_csv(path)
    except Exception:
        df = pd.DataFrame(columns=headers)
    for h in headers:
        if h not in df.columns:
            df[h] = pd.NA
    df = df[headers]
    df.to_csv(path, index=False)


def append_rows(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    ensure_schema(path, headers)
    if not rows:
        return
    df = pd.DataFrame(rows)
    for h in headers:
        if h not in df.columns:
            df[h] = pd.NA
    df = df[headers]
    df.to_csv(path, mode="a", header=False, index=False)


def align_to_ny_date(ts: str | datetime) -> str:
    dt = pd.Timestamp(ts)
    if dt.tzinfo is None:
        dt = dt.tz_localize("UTC")
    return dt.tz_convert(NY_TZ).strftime("%Y-%m-%d")


def compute_pnl_daily(executions_rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not executions_rows:
        return pd.DataFrame(columns=PNL_DAILY_HEADERS)
    df = pd.DataFrame(executions_rows)
    if "timestamp" not in df.columns:
        return pd.DataFrame(columns=PNL_DAILY_HEADERS)
    df["day_ny"] = df["timestamp"].map(align_to_ny_date)
    df["realized_pnl"] = pd.to_numeric(df.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
    df["unrealized_pnl"] = pd.to_numeric(df.get("unrealized_pnl", 0.0), errors="coerce").fillna(0.0)
    out = (
        df.groupby("day_ny", as_index=False)[["realized_pnl", "unrealized_pnl"]]
        .sum()
        .sort_values("day_ny")
        .reset_index(drop=True)
    )
    out["total_pnl"] = out["realized_pnl"] + out["unrealized_pnl"]
    return out[PNL_DAILY_HEADERS]


def write_orders_csv(data_dir: Path, rows: list[dict[str, Any]]) -> Path:
    path = data_dir / "orders.csv"
    append_rows(path, rows, ORDERS_HEADERS)
    return path


def write_signals_csv(data_dir: Path, rows: list[dict[str, Any]]) -> Path:
    path = data_dir / "signals.csv"
    append_rows(path, rows, SIGNALS_HEADERS)
    return path


def write_positions_csv(data_dir: Path, rows: list[dict[str, Any]]) -> Path:
    path = data_dir / "positions_snapshots.csv"
    append_rows(path, rows, POSITIONS_HEADERS)
    return path


def write_pnl_daily_csv(data_dir: Path, executions_rows: list[dict[str, Any]]) -> Path:
    path = data_dir / "pnl_daily.csv"
    ensure_schema(path, PNL_DAILY_HEADERS)
    out = compute_pnl_daily(executions_rows)
    out.to_csv(path, index=False)
    return path


def write_win_rate_csv(data_dir: Path, rows: list[dict[str, Any]]) -> Path:
    path = data_dir / "win_rate.csv"
    append_rows(path, rows, WIN_RATE_HEADERS)
    return path


def write_run_log(data_dir: Path, event: dict[str, Any]) -> Path:
    path = data_dir / "run_log.jsonl"
    data_dir.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")
    return path


def now_ny_iso(now_utc: datetime) -> str:
    return to_new_york(now_utc).isoformat()
