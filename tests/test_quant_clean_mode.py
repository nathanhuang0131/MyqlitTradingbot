from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import importlib
import pandas as pd

from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.scalping_strategy import ScalpingStrategy
from qlib_tradingbot.core.data_provider import AlpacaDataProvider, DataProvider
from qlib_tradingbot.core.portfolio_risk import RiskLimits, apply_portfolio_constraints
from qlib_tradingbot.core.qlib_signal_engine import QlibSignalEngine


class _FakeTradeClient:
    def get_all_positions(self):
        return []


def test_qlib_signal_engine_stub(tmp_path: Path):
    engine = QlibSignalEngine(data_root=tmp_path)
    out = engine.run(["MSFT", "AAPL", "SPY"], stub=True)
    assert list(out.columns) == ["symbol", "timestamp", "alpha", "direction", "confidence", "horizon", "model_id"]
    assert out["alpha"].is_monotonic_decreasing
    assert set(out["symbol"]) == {"AAPL", "MSFT", "SPY"}


def test_strategy_uses_qlib_ranking(monkeypatch, tmp_path: Path):
    called = {"symbols": []}

    def _fake_engine_run(self, symbols, **_kwargs):
        _ = symbols
        return pd.DataFrame(
            [
                {"symbol": "MSFT", "timestamp": "2026-03-02T14:55:00Z", "alpha": 0.8, "direction": "BUY", "confidence": 0.8, "horizon": "1D", "model_id": "m"},
                {"symbol": "AAPL", "timestamp": "2026-03-02T14:55:00Z", "alpha": 0.4, "direction": "BUY", "confidence": 0.4, "horizon": "1D", "model_id": "m"},
                {"symbol": "TSLA", "timestamp": "2026-03-02T14:55:00Z", "alpha": -0.2, "direction": "SELL", "confidence": 0.2, "horizon": "1D", "model_id": "m"},
            ]
        )

    def _fake_1m(_dc, *, symbols, lookback_days, cfg):
        _ = lookback_days, cfg
        called["symbols"] = list(symbols)
        return {
            s: pd.DataFrame({"close": [100.0], "high": [101.0], "low": [99.0]})
            for s in symbols
        }

    monkeypatch.setattr("qlib_tradingbot.Strategies.scalping_strategy.QlibSignalEngine.run", _fake_engine_run)
    monkeypatch.setattr("qlib_tradingbot.Strategies.scalping_strategy.fetch_1m_bars_batch", _fake_1m)
    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.scalping_strategy.signals_from_bias_and_1m_trigger",
        lambda *a, **k: type("Sel", (), {"signals": [], "snapshot": pd.DataFrame()})(),
    )

    ctx = StrategyContext(
        run_id="g3c",
        correlation_id="g3c",
        now_utc=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        config={"scalping_window_start_ny": "09:30", "scalping_window_end_ny": "11:00"},
        data_client=object(),
        trade_client=_FakeTradeClient(),
    )
    s = ScalpingStrategy(ctx)
    _ = s.generate_signals(s.prepare_features(["AAPL", "MSFT", "TSLA"]))

    assert called["symbols"] == ["MSFT", "AAPL", "TSLA"]


def test_portfolio_risk_constraints():
    frame = pd.DataFrame(
        [
            {"symbol": "AAPL", "alpha": 0.9, "confidence": 0.9},
            {"symbol": "MSFT", "alpha": 0.8, "confidence": 0.3},
            {"symbol": "TSLA", "alpha": 0.7, "confidence": 0.4},
        ]
    )
    accepted, rejected = apply_portfolio_constraints(frame, RiskLimits(max_positions=2, max_exposure=1.1, min_confidence=0.35))

    assert accepted["symbol"].tolist() == ["AAPL"]
    assert sorted(rejected["rejection_reason"].astype(str).tolist()) == ["below_min_confidence", "max_exposure"]


def test_dashboard_imports():
    modules = [
        "qlib_tradingbot.apps.dashboard_app",
        "qlib_tradingbot.dashboards.pages.1_Account",
        "qlib_tradingbot.dashboards.pages.2_Market",
        "qlib_tradingbot.dashboards.pages.3_FundFlows",
    ]
    for mod in modules:
        loaded = importlib.import_module(mod)
        assert loaded is not None


def test_data_provider_refresh_cache_offline(tmp_path: Path):
    provider = DataProvider(data_root=tmp_path)
    written = provider.refresh_market_cache(["SPY", "QQQ"])
    assert len(written) == 2
    assert (tmp_path / "market" / "SPY.csv").exists()


def test_alpaca_provider_lazy_import_in_tests(monkeypatch, tmp_path: Path):
    def _fail(_name):
        raise AssertionError("alpaca import should remain lazy and optional")

    monkeypatch.setattr("qlib_tradingbot.core.data_provider.import_module", _fail)
    provider = AlpacaDataProvider(data_root=tmp_path)
    snap = provider.get_account_snapshot(paper=True)
    assert snap.equity == 0.0
