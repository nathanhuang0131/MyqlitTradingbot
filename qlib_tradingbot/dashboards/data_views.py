from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from qlib_tradingbot.bootstrap.settings import is_broker_configured

MACRO_SYMBOLS = ["SPY", "QQQ", "US10Y", "DXY", "GOLD", "SILVER", "BTC"]


def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _to_float(value: Any) -> float | None:
    try:
        f = float(value)
        if pd.isna(f):
            return None
        return f
    except Exception:
        return None


def _last_row(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    return df.iloc[-1].to_dict()


def load_account_view(root: Path) -> dict[str, Any]:
    orders = read_csv_safe(root / "orders.csv")
    order_events = read_csv_safe(root / "order_events.csv")
    pnl_daily = read_csv_safe(root / "performance" / "pnl_daily.csv")
    win_rate = read_csv_safe(root / "performance" / "win_rate.csv")
    positions = read_csv_safe(root / "positions_snapshots.csv")
    trades = read_csv_safe(root / "trades_ledger.csv")
    run_log = read_csv_safe(root / "run_log.jsonl")
    if run_log.empty and (root / "run_log.jsonl").exists():
        try:
            run_log = pd.read_json(root / "run_log.jsonl", lines=True)
        except Exception:
            run_log = pd.DataFrame()

    latest_pos = _last_row(positions)
    latest_win = _last_row(win_rate)
    latest_pnl = _last_row(pnl_daily)
    latest_run = _last_row(run_log)

    unrealized = _to_float(positions.get("unrealized_pl", pd.Series(dtype=float)).sum()) if not positions.empty else None
    realized = _to_float(latest_pnl.get("realized_pnl"))
    total = None if realized is None and unrealized is None else (realized or 0.0) + (unrealized or 0.0)

    pending = 0
    if not orders.empty and "status" in orders.columns:
        pending = int(
            (~orders["status"].astype(str).str.lower().isin({"ok", "filled", "cancelled", "canceled", "rejected"})).sum()
        )

    latest_ts = str(latest_pos.get("timestamp_ny") or "")
    open_positions = 0
    if not positions.empty and latest_ts and "timestamp_ny" in positions.columns:
        open_positions = int((positions["timestamp_ny"].astype(str) == latest_ts).sum())

    exposure = pd.DataFrame()
    if not trades.empty:
        by_strategy = trades.groupby("strategy", dropna=False).size().reset_index(name="trades")
        by_strategy["type"] = "strategy"
        by_side = trades.groupby("side", dropna=False).size().reset_index(name="trades").rename(columns={"side": "strategy"})
        by_side["type"] = "side"
        exposure = pd.concat([by_strategy, by_side], ignore_index=True)

    return {
        "metrics": {
            "equity": _to_float(latest_pos.get("market_value")),
            "cash": None,
            "buying_power": None,
            "open_positions": open_positions,
            "pending_orders": pending,
            "realized_pnl_daily": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": total,
            "win_rate": _to_float(latest_win.get("win_rate")),
            "market_open": bool(latest_run.get("market_open")) if latest_run else None,
            "within_window": bool(latest_run.get("within_window")) if latest_run else None,
            "dry_run": latest_run.get("dry_run_effective") if latest_run else None,
            "broker_configured": is_broker_configured(),
            "last_run_id": latest_run.get("run_id") if latest_run else None,
        },
        "pnl_daily": pnl_daily,
        "recent_orders": order_events.tail(50) if not order_events.empty else orders.tail(50),
        "exposure": exposure,
    }


def load_market_view(root: Path) -> dict[str, Any]:
    market_root = root / "market"
    macro_rows: list[dict[str, Any]] = []
    for sym in MACRO_SYMBOLS:
        df = read_csv_safe(market_root / f"{sym}.csv")
        if df.empty:
            macro_rows.append({"symbol": sym, "close": None, "move_pct": None})
            continue
        close_col = "close" if "close" in df.columns else (df.columns[-1] if len(df.columns) > 0 else None)
        if close_col is None:
            macro_rows.append({"symbol": sym, "close": None, "move_pct": None})
            continue
        close_series = pd.to_numeric(df[close_col], errors="coerce").dropna()
        close = float(close_series.iloc[-1]) if not close_series.empty else None
        move = None
        if len(close_series) >= 2:
            prev = float(close_series.iloc[-2])
            if prev:
                move = ((float(close_series.iloc[-1]) / prev) - 1.0) * 100.0
        macro_rows.append({"symbol": sym, "close": close, "move_pct": move})

    sig = read_csv_safe(root / "signals" / "intraday_3alpha_signals.csv")
    watch = pd.DataFrame()
    movers = pd.DataFrame()
    alpha = pd.DataFrame()
    if not sig.empty:
        sig = sig.copy()
        if "intraday_return" in sig.columns:
            sig["move_pct"] = pd.to_numeric(sig["intraday_return"], errors="coerce") * 100.0
        elif "ret_1" in sig.columns:
            sig["move_pct"] = pd.to_numeric(sig["ret_1"], errors="coerce") * 100.0
        watch_cols = [c for c in ["symbol", "close_last", "dollar_vol", "vol_ratio_1", "move_pct"] if c in sig.columns]
        alpha_cols = [c for c in ["symbol", "alpha_ml", "alpha_mr", "alpha_mom", "alpha_total"] if c in sig.columns]
        if watch_cols:
            watch = sig[watch_cols].copy()
            movers = watch.sort_values("move_pct", ascending=False, na_position="last").head(20) if "move_pct" in watch.columns else watch.head(20)
        if alpha_cols:
            alpha = sig[alpha_cols].copy().sort_values("alpha_total", ascending=False, na_position="last") if "alpha_total" in alpha_cols else sig[alpha_cols].copy()

    stage_trace = read_csv_safe(root / "stage_trace.csv")
    stage_funnel = pd.DataFrame()
    if not stage_trace.empty and {"run_id", "stage"}.issubset(stage_trace.columns):
        latest_run_id = str(stage_trace["run_id"].astype(str).iloc[-1])
        run_df = stage_trace[stage_trace["run_id"].astype(str) == latest_run_id].copy()
        if not run_df.empty:
            if "metrics_json" in run_df.columns:
                run_df["metrics_json"] = run_df["metrics_json"].astype(str)
            stage_funnel = run_df.groupby("stage", dropna=False).size().reset_index(name="events")

    return {
        "macro": pd.DataFrame(macro_rows),
        "watchlist": watch,
        "top_movers": movers,
        "alpha": alpha,
        "stage_funnel": stage_funnel,
    }


def load_fund_flows_view(root: Path) -> dict[str, Any]:
    flows = read_csv_safe(root / "market" / "fund_flows_proxy.csv")
    positioning = read_csv_safe(root / "market" / "positioning_proxy.csv")

    risk_signal = "No flow proxies available."
    if not flows.empty and "flow_usd_m" in flows.columns:
        flow_sum = pd.to_numeric(flows["flow_usd_m"], errors="coerce").fillna(0.0).sum()
        risk_signal = "Risk-on tilt from positive net flows." if flow_sum >= 0 else "Risk-off tilt from negative net flows."

    sector_signal = "Sector rotation summary unavailable."
    if not positioning.empty:
        top_col = "segment" if "segment" in positioning.columns else positioning.columns[0]
        metric_col = "net_position" if "net_position" in positioning.columns else positioning.columns[-1]
        try:
            best = positioning.sort_values(metric_col, ascending=False).iloc[0]
            sector_signal = f"Positioning strongest in {best[top_col]}."
        except Exception:
            pass

    return {
        "flows": flows,
        "positioning": positioning,
        "risk_box": risk_signal,
        "rotation_box": sector_signal,
    }
