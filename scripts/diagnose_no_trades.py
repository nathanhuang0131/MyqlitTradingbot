from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qlib_tradingbot.Diagnostics.no_trades import analyze_last_run
from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher
from qlib_tradingbot.Strategies.registry import default_registry
from qlib_tradingbot.Utils.timezone_utils import to_new_york
from qlib_tradingbot.config import DRY_RUN, PAPER
from qlib_tradingbot.orchestrator import Orchestrator


@dataclass
class _Clock:
    is_open: bool = True
    next_open: datetime | None = None
    next_close: datetime | None = None


class _FakePosition:
    def __init__(self, symbol: str, qty: float = 1.0) -> None:
        self.symbol = symbol
        self.qty = qty


class _FakeTradeClient:
    def __init__(self, *, market_open: bool, positions: list[_FakePosition]) -> None:
        self._clock = _Clock(is_open=market_open)
        self._positions = positions
        self.submits: list[Any] = []

    def get_clock(self):
        return self._clock

    def get_all_positions(self):
        return list(self._positions)

    def submit_order(self, order_req):
        self.submits.append(order_req)
        return {"id": f"FAKE-{len(self.submits)}"}


def _parse_now(now_utc: str | None) -> datetime:
    if not now_utc:
        return datetime.now(timezone.utc)
    ts = datetime.fromisoformat(now_utc.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _build_live_clients() -> tuple[Any, Any]:
    try:
        from qlib_tradingbot.Brokers.alpaca_clients import build_clients

        return build_clients(paper=PAPER)
    except Exception:
        return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnose why no trades were submitted")
    ap.add_argument("--strategy", default="intraday", choices=["intraday", "intraday_3alpha", "scalping", "short-term", "long-term"])
    ap.add_argument("--data-dir", default="Data")
    ap.add_argument("--now-utc", default=None, help="ISO UTC timestamp, e.g. 2026-03-06T14:30:00Z")
    ap.add_argument("--positions", type=int, default=0, help="Offline fake held positions count")
    ap.add_argument("--market-open", action="store_true", default=True)
    ap.add_argument("--offline", action="store_true", default=False, help="Run with fake clients.")
    ap.add_argument("--live", action="store_true", default=False, help="Use Alpaca clients if configured.")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    now_utc = _parse_now(args.now_utc)
    now_ny = to_new_york(now_utc)

    print("=== Diagnose No Trades ===")
    print(f"UTC now: {now_utc.isoformat()}")
    print(f"NY now:  {now_ny.isoformat()}")
    print("UI default NY window: 09:30-11:00")
    print(f"env DRY_RUN={DRY_RUN} PAPER={PAPER}")
    if os.getenv("DRY_RUN", "1") == "1":
        print("Warning: DRY_RUN env is 1; live broker submissions are disabled.")

    if args.strategy == "intraday":
        print("Intraday strategy behavior: SELL held positions only, after 15:55 NY, no BUY entries.")

    use_live = bool(args.live and not args.offline)
    if use_live:
        data_client, trade_client = _build_live_clients()
        if trade_client is None:
            print("Live mode unavailable (missing keys or Alpaca client error). Falling back to offline fakes.")
            fake_positions = [_FakePosition(f"SYM{i+1}") for i in range(max(0, int(args.positions)))]
            data_client, trade_client = object(), _FakeTradeClient(market_open=bool(args.market_open), positions=fake_positions)
    else:
        fake_positions = [_FakePosition(f"SYM{i+1}") for i in range(max(0, int(args.positions)))]
        data_client, trade_client = object(), _FakeTradeClient(market_open=bool(args.market_open), positions=fake_positions)

    held = len(trade_client.get_all_positions()) if hasattr(trade_client, "get_all_positions") else 0
    print(f"Held positions: {held}")

    cfg = {
        "dry_run": bool(DRY_RUN),
        "force_eod_flat": True,
        "scalping_window_start_ny": "09:30",
        "scalping_window_end_ny": "11:00",
        "allow_shorts": False,
        "buy_threshold": 0.05,
        "sell_threshold": -0.05,
        "universe_symbols": [] if args.strategy == "intraday" else ["AAPL", "MSFT", "SPY"],
    }

    ctx = StrategyContext(
        run_id=now_utc.strftime("%Y%m%dT%H%M%SZ"),
        correlation_id=f"diag-{now_utc.strftime('%H%M%S')}",
        now_utc=now_utc,
        data_dir=str(data_dir),
        iteration=1,
        config=cfg,
        data_client=data_client,
        trade_client=trade_client,
    )
    dispatcher = StrategyDispatcher(default_registry().factories())
    orch = Orchestrator(dispatcher=dispatcher)
    result = orch.run_once(args.strategy, ctx)
    summary = dict(result.get("execution_summary", {}) or {})

    print("\nEXECUTION_SUMMARY")
    for key in [
        "run_id",
        "strategy",
        "gate_status",
        "market_open",
        "within_window",
        "stage1_symbols",
        "signals_total",
        "orders_attempted",
        "orders_submitted",
        "dry_run_env",
        "dry_run_effective",
        "trace_file_path",
    ]:
        print(f"{key}: {summary.get(key)}")

    diagnosis = analyze_last_run(data_dir, str(summary.get("run_id") or ""))
    print("\nNo Trades Explanation")
    for code in diagnosis.get("top_reason_codes", []):
        print(f"- {code}")
    for line in diagnosis.get("explanations", []):
        print(f"  * {line}")
    print(f"counters: {diagnosis.get('counters', {})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
