from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.scalping_strategy import ScalpingStrategy


class _FakeTradeClient:
    def get_all_positions(self):
        return []


def _make_ctx(now_utc: datetime) -> StrategyContext:
    return StrategyContext(
        run_id="run-1",
        correlation_id="corr-1",
        now_utc=now_utc,
        data_client=object(),
        trade_client=_FakeTradeClient(),
        config={
            "scalping_window_start_ny": "09:30",
            "scalping_window_end_ny": "11:00",
            "top_n_signals": 3,
        },
    )


def test_scalping_strategy_skips_outside_window(monkeypatch):
    now_utc = datetime(2026, 3, 2, 17, 0, tzinfo=timezone.utc)  # 12:00 NY
    strategy = ScalpingStrategy(_make_ctx(now_utc))

    calls = {"engine": 0}

    def _fake_engine_run(*args, **kwargs):
        calls["engine"] += 1
        return pd.DataFrame(columns=["symbol", "timestamp", "alpha", "direction", "confidence", "horizon", "model_id"])

    monkeypatch.setattr("qlib_tradingbot.Strategies.scalping_strategy.QlibSignalEngine.run", _fake_engine_run)
    features = strategy.prepare_features(["AAPL"])
    signals = strategy.generate_signals(features)
    assert signals == []
    assert calls["engine"] == 0


def test_scalping_strategy_uses_5m_bias_and_1m_trigger(monkeypatch):
    now_utc = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)  # 10:00 NY
    strategy = ScalpingStrategy(_make_ctx(now_utc))

    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.scalping_strategy.QlibSignalEngine.run",
        lambda *a, **k: pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "timestamp": "2026-03-02T14:55:00Z",
                    "alpha": 0.01,
                    "direction": "BUY",
                    "confidence": 0.01,
                    "horizon": "1D",
                    "model_id": "stub",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.scalping_strategy.fetch_1m_bars_batch",
        lambda *a, **k: {"AAPL": pd.DataFrame({"close": [100.0], "high": [100.1], "low": [99.9]})},
    )
    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.scalping_strategy.signals_from_bias_and_1m_trigger",
        lambda *a, **k: type("Sel", (), {"signals": ["ok"], "snapshot": pd.DataFrame()})(),
    )

    features = strategy.prepare_features(["AAPL"])
    signals = strategy.generate_signals(features)
    assert signals == ["ok"]
