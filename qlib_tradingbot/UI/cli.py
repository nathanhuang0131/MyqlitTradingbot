from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.Brokers.alpaca_clients import build_clients
from qlib_tradingbot.Analytics.performance import (
    breakdown_by_strategy,
    breakdown_by_symbol,
    daily_pnl,
    load_trades,
    win_rate,
)
from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher
from qlib_tradingbot.Strategies.registry import default_registry
from qlib_tradingbot.Utils.timezone_utils import format_session_window
from qlib_tradingbot.config import DATA_DIR, DRY_RUN, PAPER
from qlib_tradingbot.orchestrator import Orchestrator


def _prompt_int(label: str, default: int) -> int:
    value = input(f"{label} [{default}]: ").strip()
    return int(value) if value else int(default)


def _prompt_float(label: str, default: float) -> float:
    value = input(f"{label} [{default}]: ").strip()
    return float(value) if value else float(default)


def _prompt_text(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value if value else default


def _prompt_bool(label: str, default: bool) -> bool:
    s = "Y/n" if default else "y/N"
    value = input(f"{label} ({s}): ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "1", "true"}


def _select_strategy() -> str:
    print("Select strategy:")
    print("  1) Long-term")
    print("  2) Short-term")
    print("  3) Intraday")
    print("  4) Scalping (5m bias + 1m trigger)")
    print("  5) View Performance Analytics")
    pick = input("Choice [1-5]: ").strip()
    mapping = {"1": "long-term", "2": "short-term", "3": "intraday", "4": "scalping", "5": "__analytics__"}
    return mapping.get(pick, "long-term")


def build_runtime_config(strategy_name: str) -> dict[str, object]:
    window_start = _prompt_text("Trading window start (NY, HH:MM)", "09:30")
    window_end = _prompt_text("Trading window end (NY, HH:MM)", "11:00")
    loop_mode = _prompt_bool("Loop mode", False)
    loop_sleep_sec = _prompt_int("Loop sleep seconds", 60)
    max_symbols = _prompt_int("Max symbols", 100)
    max_positions = _prompt_int("Max positions", 5)
    dollars_per_trade = _prompt_float("Dollars per trade", 250.0)
    allow_shorts = _prompt_bool("Enable short selling?", False) if strategy_name == "scalping" else False
    return {
        "scalping_window_start_ny": window_start,
        "scalping_window_end_ny": window_end,
        "loop_mode": loop_mode,
        "loop_sleep_sec": loop_sleep_sec,
        "max_symbols": max_symbols,
        "max_positions": max_positions,
        "dollars_per_trade": dollars_per_trade,
        "allow_shorts": allow_shorts,
    }


def build_analytics_view(choice: str, trades_df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    if choice == "1":
        return ("Daily P&L", daily_pnl(trades_df))
    if choice == "2":
        wr = win_rate(trades_df)
        return ("Win Rate", pd.DataFrame([wr]))
    if choice == "3":
        return ("By Symbol", breakdown_by_symbol(trades_df))
    if choice == "4":
        return ("By Strategy", breakdown_by_strategy(trades_df))
    return ("Unknown Option", pd.DataFrame())


def run_analytics_cli(data_dir: Path) -> None:
    ledger = data_dir / "trades_ledger.csv"
    trades_df = load_trades(ledger)
    print("\nPerformance Analytics")
    print("  1) Daily P&L")
    print("  2) Win rate")
    print("  3) By symbol")
    print("  4) By strategy")
    pick = input("Choice [1-4]: ").strip()
    title, table = build_analytics_view(pick, trades_df)
    print(f"\n{title}")
    if table.empty:
        print("No data available.")
        return
    print(table.to_string(index=False))


def run_once_interactive() -> None:
    print("\n=== QLIB TradingBot Unified Runner ===\n")
    print(f"Paper: {PAPER} | DRY_RUN: {DRY_RUN}\n")

    strategy_name = _select_strategy()
    if strategy_name == "__analytics__":
        run_analytics_cli(Path(DATA_DIR))
        return

    cfg = build_runtime_config(strategy_name)
    loop_mode = bool(cfg.get("loop_mode", False))
    loop_sleep_sec = int(cfg.get("loop_sleep_sec", 60))

    now_utc = datetime.now(timezone.utc)
    print(
        format_session_window(
            now_utc,
            str(cfg.get("scalping_window_start_ny", "09:30")),
            str(cfg.get("scalping_window_end_ny", "11:00")),
        )
    )
    print(f"allow_shorts={bool(cfg.get('allow_shorts', False))}")

    data_client, trade_client = build_clients(paper=PAPER)

    dispatcher = StrategyDispatcher(default_registry().factories())
    orchestrator = Orchestrator(dispatcher=dispatcher)

    while True:
        ctx = StrategyContext(
            run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            correlation_id=datetime.now(timezone.utc).strftime("corr-%H%M%S"),
            now_utc=datetime.now(timezone.utc),
            data_dir=str(DATA_DIR),
            config=cfg,
            data_client=data_client,
            trade_client=trade_client,
        )
        result = orchestrator.run_once(strategy_name, ctx)
        print(result)
        if not loop_mode:
            break
        time.sleep(max(5, int(loop_sleep_sec)))
