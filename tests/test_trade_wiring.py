from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.Execution import orders
from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher
from qlib_tradingbot.Strategies.registry import default_registry
from qlib_tradingbot.Strategies.scalping_strategy import ScalpingStrategy
from qlib_tradingbot.orchestrator import Orchestrator


class _LiveFakeTradeClient:
    def __init__(self) -> None:
        self.submit_calls: list[object] = []

    def get_clock(self):
        return type("Clock", (), {"is_open": True})()

    def get_all_positions(self):
        return []

    def submit_order(self, order_req):
        self.submit_calls.append(order_req)
        return {"id": f"LIVE-{len(self.submit_calls)}"}


def test_non_dry_run_simple_submit_works_with_fake_client_without_alpaca(monkeypatch):
    trade_client = _LiveFakeTradeClient()
    monkeypatch.setattr(orders, "DRY_RUN", False)

    def _missing_alpaca():
        raise ModuleNotFoundError("alpaca not installed")

    monkeypatch.setattr(orders, "_import_alpaca", _missing_alpaca)
    result = orders.place_simple_buy(trade_client, symbol="AAPL", qty=1)

    assert result.ok is True
    assert result.submitted is True
    assert len(trade_client.submit_calls) == 1


def test_forced_signal_reaches_submit_path_when_dry_run_false(monkeypatch, tmp_path: Path):
    trade_client = _LiveFakeTradeClient()

    monkeypatch.setattr(ScalpingStrategy, "build_universe", lambda self: ["AAPL"])
    monkeypatch.setattr(
        ScalpingStrategy,
        "prepare_features",
        lambda self, universe: {"universe": universe},
    )
    monkeypatch.setattr(
        ScalpingStrategy,
        "generate_signals",
        lambda self, _features: [
            Signal(
                symbol="AAPL",
                side="BUY",
                strategy_id="scalping",
                strategy_version="1.0",
                timeframe="1Min",
                price_basis=100.0,
                correlation_id=self.ctx.correlation_id,
                run_id=self.ctx.run_id,
                features={"intent_order_type": "SIMPLE_BUY", "dollars": 250.0},
            )
        ],
    )

    dispatcher = StrategyDispatcher(default_registry().factories())
    orch = Orchestrator(dispatcher=dispatcher)
    ctx = StrategyContext(
        run_id="run-wire-1",
        correlation_id="corr-wire-1",
        now_utc=datetime(2026, 3, 6, 15, 5, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        iteration=1,
        config={
            "dry_run": False,
            "scalping_window_start_ny": "00:00",
            "scalping_window_end_ny": "23:59",
            "allow_shorts": False,
            "dollars_per_trade": 250.0,
        },
        data_client=object(),
        trade_client=trade_client,
    )

    out = orch.run_once("scalping", ctx)
    summary = out["execution_summary"]

    assert out["status"] == "ok"
    assert summary["orders_attempted"] == 1
    assert summary["orders_submitted"] == 1
    assert summary["dry_run_effective"] is False
    assert len(trade_client.submit_calls) == 1

    orders_path = tmp_path / "orders.csv"
    assert orders_path.exists()
    orders_df = pd.read_csv(orders_path)
    assert not orders_df.empty
    assert "run_id" in orders_df.columns
    assert "correlation_id" in orders_df.columns
    assert str(out["run_id"]) in set(orders_df["run_id"].astype(str))
    assert "corr-wire-1" in set(orders_df["correlation_id"].astype(str))
