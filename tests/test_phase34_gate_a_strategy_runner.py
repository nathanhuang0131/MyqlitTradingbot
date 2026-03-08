from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Execution.strategy_runner import StrategyRunner
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext


class _FakeTradeClient:
    def __init__(self) -> None:
        self.submit_calls = 0

    def get_all_positions(self):
        return []

    def submit_order(self, _order_req):
        self.submit_calls += 1
        return {"id": "LIVE-ORDER"}


class _StubStrategy(StrategyBase):
    strategy_id = "stub-phase34-a"

    def build_universe(self):
        return ["AAPL", "MSFT"]

    def prepare_features(self, universe):
        return {"universe": universe}

    def generate_signals(self, features):
        symbols = list(features.get("universe") or [])
        return [
            Signal(symbol=symbols[0], side="BUY", strategy_id=self.strategy_id, strategy_version="1", timeframe="1Min", price_basis=100.0),
            Signal(symbol=symbols[1], side="BUY", strategy_id=self.strategy_id, strategy_version="1", timeframe="1Min", price_basis=200.0),
        ]

    def execute(self, signals):
        return signals

    def post_trade_reporting(self):
        return {}


def test_strategy_runner_mock_broker_integration(tmp_path: Path):
    trade_client = _FakeTradeClient()
    ctx = StrategyContext(
        run_id="run-gate-a",
        correlation_id="corr-gate-a",
        now_utc=datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        config={"dry_run": True},
        trade_client=trade_client,
    )
    strategy = _StubStrategy()
    runner = StrategyRunner()

    result = runner.run_once(
        strategy,
        ctx,
        dry_run=True,
        dry_run_output_dir=tmp_path / "trade_history",
    )

    assert result.strategy_id == "stub-phase34-a"
    assert result.universe_size == 2
    assert result.signals_size == 2
    assert result.orders_size == 2
    assert all(o.ok for o in result.orders)
    assert all(not o.submitted for o in result.orders)
    assert trade_client.submit_calls == 0
    assert (tmp_path / "trade_history" / "mock_orders.csv").is_file()
    assert (tmp_path / "trade_history" / "mock_orders.jsonl").is_file()
