from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher
from qlib_tradingbot.Strategies.registry import default_registry
from qlib_tradingbot.UI import cli
from qlib_tradingbot.orchestrator import Orchestrator


class _OpenTradeClient:
    def get_clock(self):
        return type("Clock", (), {"is_open": True})()

    def get_all_positions(self):
        return []

    def submit_order(self, _order_req):
        return {"id": "ORDER-1"}


def test_ui_select_strategy_includes_intraday_3alpha(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "7")
    assert cli._select_strategy() == "intraday_3alpha"


def test_orchestrator_intraday_3alpha_offline_smoke_writes_stage_trace(tmp_path: Path):
    dispatcher = StrategyDispatcher(default_registry().factories())
    orch = Orchestrator(dispatcher=dispatcher)
    ctx = StrategyContext(
        run_id="run-intraday-3alpha",
        correlation_id="corr-intraday-3alpha",
        now_utc=datetime(2026, 3, 6, 15, 0, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        iteration=1,
        config={
            "dry_run": True,
            "universe_symbols": ["AAPL", "MSFT", "SPY"],
            "allow_shorts": False,
            "buy_threshold": 0.05,
            "sell_threshold": -0.05,
        },
        data_client=object(),
        trade_client=_OpenTradeClient(),
    )

    out = orch.run_once("intraday_3alpha", ctx)

    assert out["status"] == "ok"
    trace_csv = tmp_path / "stage_trace.csv"
    assert trace_csv.exists()
    trace_df = pd.read_csv(trace_csv)
    assert not trace_df.empty
    assert "run_id" in trace_df.columns
    assert out["run_id"] in set(trace_df["run_id"].astype(str))
    assert {"stage0_gate", "stage1_universe", "stage3_signals", "stage3_execution"}.issubset(
        set(trace_df["stage"].astype(str))
    )
