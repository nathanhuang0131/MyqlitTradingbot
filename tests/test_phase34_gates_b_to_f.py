from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.core.models import OrderIntent, Signal
from qlib_tradingbot.Execution import orders
from qlib_tradingbot.Execution.engine import execute_intent, execute_signals
from qlib_tradingbot.Execution.risk_manager import apply_signal_risk_controls
from qlib_tradingbot.Execution.strategy_runner import StrategyRunner
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher
from qlib_tradingbot.Strategies.llm_planner_strategy import LLMPlannerStrategy
from qlib_tradingbot.orchestrator import Orchestrator
from qlib_tradingbot.Tools.perf_report import write_performance_reports


class _NoopTradeClient:
    def __init__(self):
        self.submit_payloads: list[dict] = []

    def get_all_positions(self):
        return []

    def submit_order(self, req):
        self.submit_payloads.append(req)
        return {"id": f"OID-{len(self.submit_payloads)}"}


class _FeedbackStrategy(StrategyBase):
    strategy_id = "feedback-gate"

    def build_universe(self):
        return ["AAPL", "TSLA"]

    def prepare_features(self, universe):
        return {"universe": universe}

    def generate_signals(self, _features):
        return [
            Signal(symbol="AAPL", side="BUY", strategy_id=self.strategy_id, strategy_version="1", timeframe="1Min", price_basis=100.0),
            Signal(symbol="TSLA", side="BUY", strategy_id=self.strategy_id, strategy_version="1", timeframe="1Min", price_basis=200.0),
        ]

    def execute(self, signals):
        return signals

    def post_trade_reporting(self):
        return {}


def test_gate_b_risk_manager_sizing_stop_and_rejection_reasons():
    signals = [
        Signal(symbol="AAPL", side="BUY", strategy_id="S", strategy_version="1", timeframe="1Min", price_basis=100.0, features={"dollars": 500.0}),
        Signal(symbol="MSFT", side="BUY", strategy_id="S", strategy_version="1", timeframe="1Min", price_basis=0.0),
        Signal(symbol="NVDA", side="BUY", strategy_id="S", strategy_version="1", timeframe="1Min", price_basis=50.0, features={"dollars": -1.0}),
    ]
    accepted, rejected = apply_signal_risk_controls(signals, max_dollars_per_trade=250.0, stop_loss_pct=0.01)

    assert len(accepted) == 1
    assert float(accepted[0].features["dollars"]) == 250.0
    assert float(accepted[0].features["risk_stop_price"]) == 99.0
    assert sorted((r.error or "") for r in rejected) == ["invalid_dollars", "missing_price_basis_for_stop_loss"]


def test_gate_c_order_types_supported_in_mock_and_paper(monkeypatch, tmp_path: Path):
    tc = _NoopTradeClient()

    # Mock mode path: execute_signals(dry_run=True) records intended orders for advanced types.
    sigs = [
        Signal(symbol="AAPL", side="BUY", strategy_id="S", strategy_version="1", timeframe="1Min", price_basis=100.0, features={"intent_order_type": "LIMIT_BUY"}),
        Signal(symbol="MSFT", side="BUY", strategy_id="S", strategy_version="1", timeframe="1Min", price_basis=100.0, features={"intent_order_type": "STOP_BUY"}),
        Signal(symbol="NVDA", side="BUY", strategy_id="S", strategy_version="1", timeframe="1Min", price_basis=100.0, features={"intent_order_type": "STOP_LIMIT_BUY"}),
        Signal(symbol="TSLA", side="SELL", strategy_id="S", strategy_version="1", timeframe="1Min", price_basis=100.0, features={"intent_order_type": "TRAILING_STOP_SELL"}),
    ]
    mock_res = execute_signals(tc, sigs, dry_run=True, dry_run_output_dir=tmp_path / "trade_history")
    assert len(mock_res) == 4
    assert (tmp_path / "trade_history" / "mock_orders.csv").is_file()

    # Paper/live-submit path: advanced order intent submits deterministic payload.
    monkeypatch.setattr(orders, "DRY_RUN", False)
    intents = [
        OrderIntent(symbol="AAPL", side="BUY", order_type="LIMIT_BUY", qty=1, meta={"limit_price": 101.0}),
        OrderIntent(symbol="MSFT", side="BUY", order_type="STOP_BUY", qty=1, stop_price=99.0),
        OrderIntent(symbol="NVDA", side="BUY", order_type="STOP_LIMIT_BUY", qty=1, stop_price=99.0, meta={"limit_price": 98.5}),
        OrderIntent(symbol="TSLA", side="SELL", order_type="TRAILING_STOP_SELL", qty=1, meta={"trail_percent": 1.5}),
        OrderIntent(symbol="QQQ", side="BUY", order_type="MARKET_BUY", qty=1, meta={"qty": 1}),
    ]
    out = [execute_intent(tc, i) for i in intents]
    assert all(r.ok for r in out)
    assert all(r.submitted for r in out)
    assert len(tc.submit_payloads) >= 4


def test_gate_d_feedback_gating_affects_trade_intents(tmp_path: Path):
    tc = _NoopTradeClient()
    ctx = StrategyContext(
        run_id="gate-d",
        correlation_id="gate-d",
        now_utc=datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        config={
            "dry_run": True,
            "dollars_per_trade": 200.0,
            "llm_bias_state": {
                "AAPL": {"bias": "Bearish", "prob": 90.0, "action": "Exit"},
                "TSLA": {"bias": "Bullish", "prob": 90.0, "action": "Hold"},
            },
        },
        trade_client=tc,
    )
    runner = StrategyRunner()
    res = runner.run_once(_FeedbackStrategy(), ctx, dry_run=True, dry_run_output_dir=tmp_path / "trade_history")

    assert res.orders_size == 1
    assert res.orders[0].symbol == "TSLA"


class _ClosedTradeClient:
    def get_clock(self):
        return type("Clock", (), {"is_open": False})()

    def get_all_positions(self):
        return []


def test_gate_e_trading_window_market_closed_logged():
    dispatcher = StrategyDispatcher({"llm-planner": lambda ctx: LLMPlannerStrategy(ctx)})
    orch = Orchestrator(dispatcher=dispatcher)
    status = orch.run_once(
        strategy_name="llm-planner",
        ctx=StrategyContext(
            run_id="gate-e",
            now_utc=datetime(2026, 3, 2, 2, 0, tzinfo=timezone.utc),
            trade_client=_ClosedTradeClient(),
            data_client=object(),
            config={"loop_mode": False, "universe_symbols": ["AAPL"]},
        ),
    )
    assert status["status"] == "market_closed"
    assert "market closed" in str(status["execution_summary"]["gate_reason"]).lower()


def test_gate_f_performance_outputs_generated(tmp_path: Path):
    data_dir = tmp_path / "Data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "strategy": "gate-f",
                "symbol": "AAPL",
                "side": "BUY",
                "qty": 1,
                "fill_price": 100,
                "order_id": "1",
                "event": "CLOSE",
                "realized_pnl": 1.0,
                "fees": 0.0,
                "tags": "",
            }
        ]
    ).to_csv(data_dir / "trades_ledger.csv", index=False)
    pnl, win = write_performance_reports(data_dir=data_dir, out_dir=tmp_path / "performance")
    assert pnl.is_file()
    assert win.is_file()
