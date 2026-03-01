from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.Reporting.reporting import (
    ORDERS_HEADERS,
    PNL_DAILY_HEADERS,
    SIGNALS_HEADERS,
    align_to_ny_date,
    compute_pnl_daily,
    write_orders_csv,
    write_signals_csv,
)
from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher
from qlib_tradingbot.Strategies.llm_planner_strategy import LLMPlannerStrategy
from qlib_tradingbot.orchestrator import Orchestrator


class _ClosedTradeClient:
    def get_clock(self):
        return type(
            "Clock",
            (),
            {
                "is_open": False,
                "next_open": datetime(2026, 3, 2, 14, 30, tzinfo=timezone.utc),
                "next_close": datetime(2026, 3, 2, 21, 0, tzinfo=timezone.utc),
            },
        )()

    def get_all_positions(self):
        return []


def test_market_closed_smoke(capsys):
    dispatcher = StrategyDispatcher({"llm-planner": lambda ctx: LLMPlannerStrategy(ctx)})
    orch = Orchestrator(dispatcher=dispatcher)
    status = orch.run_once(
        strategy_name="llm-planner",
        ctx=StrategyContext(
            run_id="r1",
            now_utc=datetime(2026, 3, 2, 2, 0, tzinfo=timezone.utc),
            trade_client=_ClosedTradeClient(),
            data_client=object(),
            config={"loop_mode": False, "universe_symbols": ["AAPL"]},
        ),
    )
    out = capsys.readouterr().out.lower()
    assert "market closed" in out or "no regular session" in out
    assert status["status"] == "market_closed"


def test_reporting_writes_empty_csv_with_headers():
    out_dir = Path("Data/test_reporting")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_orders_csv(out_dir, [])
    write_signals_csv(out_dir, [])
    assert (out_dir / "orders.csv").exists()
    assert (out_dir / "signals.csv").exists()
    assert list(pd.read_csv(out_dir / "orders.csv").columns) == ORDERS_HEADERS
    assert list(pd.read_csv(out_dir / "signals.csv").columns) == SIGNALS_HEADERS


def test_pnl_daily_uses_ny_boundary():
    rows = [
        {"timestamp": "2026-03-02T03:50:00+00:00", "realized_pnl": 10.0, "unrealized_pnl": 1.0},  # 2026-03-01 NY
        {"timestamp": "2026-03-02T05:10:00+00:00", "realized_pnl": 4.0, "unrealized_pnl": 2.0},   # 2026-03-02 NY
    ]
    pnl = compute_pnl_daily(rows)
    assert list(pnl.columns) == PNL_DAILY_HEADERS
    assert align_to_ny_date(rows[0]["timestamp"]) != align_to_ny_date(rows[1]["timestamp"])
