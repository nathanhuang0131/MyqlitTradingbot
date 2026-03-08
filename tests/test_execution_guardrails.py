from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Execution.strategy_runner import StrategyRunner
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext


class _FakeTradeClient:
    def __init__(self):
        self.calls = 0

    def get_all_positions(self):
        return []

    def submit_order(self, _req):
        self.calls += 1
        return {"id": f"O{self.calls}"}


class _OneSignalStrategy(StrategyBase):
    strategy_id = "guardrail-test"

    def build_universe(self):
        return ["AAPL"]

    def prepare_features(self, universe):
        return {"universe": universe}

    def generate_signals(self, _features):
        return [
            Signal(
                symbol="AAPL",
                side="BUY",
                strategy_id=self.strategy_id,
                strategy_version="1.0",
                timeframe="1Min",
                score=0.9,
                price_basis=100.0,
                features={"dollars": 100.0, "qlib_model_id": "m1", "qlib_horizon": "1D"},
            )
        ]

    def execute(self, signals):
        return signals

    def post_trade_reporting(self):
        return {}


def test_blocks_non_dry_run_when_trace_write_fails(monkeypatch, tmp_path: Path):
    from qlib_tradingbot.Execution import strategy_runner as sr

    def _boom(*_args, **_kwargs):
        raise RuntimeError("trace fail")

    monkeypatch.setattr(sr, "write_decision_trace", _boom)
    tc = _FakeTradeClient()
    ctx = StrategyContext(
        run_id="g1",
        correlation_id="g1",
        now_utc=datetime(2026, 3, 8, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        config={"dry_run": False, "broker_configured": True, "dollars_per_trade": 100.0},
        trade_client=tc,
    )
    out = StrategyRunner().run_once(_OneSignalStrategy(), ctx, dry_run=False)
    assert out.orders_size >= 1
    assert tc.calls == 0
    assert any("trace" in (o.error or "").lower() for o in out.orders)


def test_blocks_non_dry_run_when_daily_loss_breached(tmp_path: Path):
    perf = tmp_path / "performance"
    perf.mkdir(parents=True, exist_ok=True)
    (perf / "pnl_daily.csv").write_text("day,realized_pnl,fees,net_pnl,trades\n2026-03-08,-1000,0,-1000,10\n", encoding="utf-8")
    tc = _FakeTradeClient()
    ctx = StrategyContext(
        run_id="g2",
        correlation_id="g2",
        now_utc=datetime(2026, 3, 8, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        config={"dry_run": False, "broker_configured": True, "daily_loss_limit": -500.0, "dollars_per_trade": 100.0},
        trade_client=tc,
    )
    out = StrategyRunner().run_once(_OneSignalStrategy(), ctx, dry_run=False)
    assert tc.calls == 0
    assert any("daily_loss_limit_breached" in (o.error or "").lower() for o in out.orders)
