from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.Brokers.alpaca_clients import build_clients, diagnose_broker_setup
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
from qlib_tradingbot.Utils.timezone_utils import format_session_window, to_new_york
from qlib_tradingbot.config import DATA_DIR, DRY_RUN, PAPER
from qlib_tradingbot.LLM.post_market_review import generate_post_market_package
from qlib_tradingbot.Diagnostics.no_trades import analyze_last_run
from qlib_tradingbot.orchestrator import Orchestrator


class ReturnToMainMenu(Exception):
    """Internal control-flow signal to restart the main interactive menu."""


STRATEGY_MENU: dict[str, tuple[str, str]] = {
    "0": ("Exit", "__exit__"),
    "1": ("Long-term", "long-term"),
    "2": ("Short-term", "short-term"),
    "3": ("Intraday (EOD Flatten)", "intraday"),
    "4": ("Scalping (5m bias + 1m trigger)", "scalping"),
    "5": ("View Performance Analytics", "__analytics__"),
    "6": ("Generate LLM post-market package", "__llm_export__"),
    "7": ("Intraday (3Alpha)", "intraday_3alpha"),
}


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
    for key, (label, _) in STRATEGY_MENU.items():
        print(f"  {key}) {label}")
    pick = input("Choice [0-7]: ").strip()
    return STRATEGY_MENU.get(pick, ("Long-term", "long-term"))[1]


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
        "dry_run": bool(DRY_RUN),
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
        print("No analytics data yet - returning to main menu.")
        return
    print(table.to_string(index=False))


def _run_selected_strategy(strategy_name: str) -> None:
    def _build_clients_or_exit():
        try:
            return build_clients(paper=PAPER)
        except Exception as exc:
            diag = diagnose_broker_setup(paper=PAPER, try_build=False)
            print(
                "Broker client initialization failed.\n"
                f"  reason: {exc}\n"
                f"  env_file: {diag.get('env_file')}\n"
                f"  broker_configured: {diag.get('broker_configured')}\n"
                f"  alpaca_available: {diag.get('alpaca_available')}\n"
                "  fix: provide APCA_API_KEY_ID/APCA_API_SECRET_KEY or "
                "ALPACA_API_KEY/ALPACA_SECRET_KEY and install alpaca-py."
            )
            raise ReturnToMainMenu from None

    if strategy_name == "__analytics__":
        run_analytics_cli(Path(DATA_DIR))
        return
    if strategy_name == "__llm_export__":
        export_strategy = _prompt_text("Strategy type for review (scalping|intraday|short-term|long-term)", "intraday")
        data_client, trade_client = _build_clients_or_exit()
        csv_path, prompt_path = generate_post_market_package(
            data_dir=Path(DATA_DIR),
            trade_client=trade_client,
            data_client=data_client,
            strategy_type=export_strategy,
        )
        print(f"Generated: {csv_path}")
        print(f"Generated: {prompt_path}")
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

    data_client, trade_client = _build_clients_or_exit()

    dispatcher = StrategyDispatcher(default_registry().factories())
    orchestrator = Orchestrator(dispatcher=dispatcher)
    iteration = 0

    def _print_execution_summary(summary: dict[str, object]) -> None:
        ny_now = to_new_york(datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")
        suppressors: list[str] = []
        run_id = str(summary.get("run_id", "") or "")
        if run_id:
            try:
                suppressors = list((analyze_last_run(Path(DATA_DIR), run_id).get("top_reason_codes") or [])[:3])
            except Exception:
                suppressors = []
        print(
            f"Cycle {summary.get('iteration', '')} ET={ny_now} "
            f"open={summary.get('market_open', False)} window={summary.get('within_window', True)} "
            f"qlib_infer={summary.get('stage2_output_size', 0)} signals={summary.get('signals_total', 0)} "
            f"orders_attempted={summary.get('orders_attempted', 0)} submitted={summary.get('orders_submitted', 0)} "
            f"dry_run={summary.get('dry_run_effective', summary.get('dry_run_env', False))}"
        )
        print("EXECUTION_SUMMARY")
        print(
            f"run_id={summary.get('run_id','')} "
            f"strategy={summary.get('strategy','')} "
            f"iter={summary.get('iteration', '')}"
        )
        print(
            f"gate={summary.get('gate_status','')} "
            f"reason={summary.get('gate_reason','')} "
            f"market_open={summary.get('market_open', False)} "
            f"within_window={summary.get('within_window', True)}"
        )
        print(
            f"stage1_symbols={summary.get('stage1_symbols', 0)} "
            f"stage2_in={summary.get('stage2_input_size', 0)} "
            f"stage2_out={summary.get('stage2_output_size', 0)} "
            f"stage2_top_filter={summary.get('stage2_top_filter', '')}"
        )
        print(
            f"final_universe={summary.get('final_universe_size', 0)} "
            f"signals={summary.get('signals_total', 0)} "
            f"orders_attempted={summary.get('orders_attempted', 0)} "
            f"orders_submitted={summary.get('orders_submitted', 0)} "
            f"dry_run_env={summary.get('dry_run_env', False)} "
            f"dry_run_effective={summary.get('dry_run_effective', False)}"
        )
        print(f"trace_file={summary.get('trace_file_path', Path(DATA_DIR) / 'stage_trace.csv')}")
        if int(summary.get("signals_total", 0) or 0) == 0 or int(summary.get("orders_submitted", 0) or 0) == 0:
            if suppressors:
                print(f"Top suppressors: {', '.join(suppressors)}")

    while True:
        iteration += 1
        try:
            ctx = StrategyContext(
                run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                correlation_id=datetime.now(timezone.utc).strftime("corr-%H%M%S"),
                now_utc=datetime.now(timezone.utc),
                data_dir=str(DATA_DIR),
                iteration=iteration,
                config=cfg,
                data_client=data_client,
                trade_client=trade_client,
            )
            result = orchestrator.run_once(strategy_name, ctx)
            _print_execution_summary(result.get("execution_summary", {}))
        except KeyboardInterrupt:
            print("Interrupted by user. Stopping current run and returning to main menu...")
            raise ReturnToMainMenu from None
        if not loop_mode:
            break
        try:
            if result.get("status") == "market_closed":
                time.sleep(max(1, int(loop_sleep_sec)))
                continue
            time.sleep(max(1, int(loop_sleep_sec)))
        except KeyboardInterrupt:
            print("Interrupted by user. Stopping current run and returning to main menu...")
            raise ReturnToMainMenu from None


def run_once_interactive() -> None:
    print("\n=== QLIB TradingBot Unified Runner ===\n")
    print(f"Paper: {PAPER} | DRY_RUN: {DRY_RUN}\n")
    strategy_name = _select_strategy()
    if strategy_name == "__exit__":
        return
    _run_selected_strategy(strategy_name)


def run_interactive() -> None:
    while True:
        print("\n=== QLIB TradingBot Unified Runner ===\n")
        print(f"Paper: {PAPER} | DRY_RUN: {DRY_RUN}\n")
        try:
            strategy_name = _select_strategy()
        except KeyboardInterrupt:
            print("\nInterrupted. Use option 0 to exit.")
            continue
        if strategy_name == "__exit__":
            print("Exiting.")
            return
        try:
            _run_selected_strategy(strategy_name)
        except ReturnToMainMenu:
            continue
        except Exception as exc:
            print(f"Unexpected error: {exc}. Returning to main menu.")
            continue
    if strategy_name == "intraday":
        print("This strategy only closes existing positions after 15:55 NY time; it does not open new positions.")
    if strategy_name == "intraday_3alpha":
        print("This strategy may open new positions based on the 3Alpha signal engine (subject to market/time/risk gates).")
