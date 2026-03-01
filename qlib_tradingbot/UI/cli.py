from __future__ import annotations

import time
from datetime import datetime, timezone

from qlib_tradingbot.Brokers.alpaca_clients import build_clients
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
    pick = input("Choice [1-4]: ").strip()
    mapping = {"1": "long-term", "2": "short-term", "3": "intraday", "4": "scalping"}
    return mapping.get(pick, "long-term")


def run_once_interactive() -> None:
    print("\n=== QLIB TradingBot Unified Runner ===\n")
    print(f"Paper: {PAPER} | DRY_RUN: {DRY_RUN}\n")

    strategy_name = _select_strategy()
    window_start = _prompt_text("Trading window start (NY, HH:MM)", "09:30")
    window_end = _prompt_text("Trading window end (NY, HH:MM)", "11:00")
    loop_mode = _prompt_bool("Loop mode", False)
    loop_sleep_sec = _prompt_int("Loop sleep seconds", 60)
    max_symbols = _prompt_int("Max symbols", 100)
    max_positions = _prompt_int("Max positions", 5)
    dollars_per_trade = _prompt_float("Dollars per trade", 250.0)

    now_utc = datetime.now(timezone.utc)
    print(format_session_window(now_utc, window_start, window_end))

    data_client, trade_client = build_clients(paper=PAPER)

    dispatcher = StrategyDispatcher(default_registry().factories())
    orchestrator = Orchestrator(dispatcher=dispatcher)

    cfg = {
        "scalping_window_start_ny": window_start,
        "scalping_window_end_ny": window_end,
        "loop_mode": loop_mode,
        "max_symbols": max_symbols,
        "max_positions": max_positions,
        "dollars_per_trade": dollars_per_trade,
    }

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
