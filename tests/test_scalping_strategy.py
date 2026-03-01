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

    calls = {"stage3": 0}

    def _fake_stage3(*args, **kwargs):
        calls["stage3"] += 1
        return pd.Series(dtype=float), pd.DataFrame()

    monkeypatch.setattr("qlib_tradingbot.Strategies.scalping_strategy.stage3_qlib_score", _fake_stage3)
    features = strategy.prepare_features(["AAPL"])
    signals = strategy.generate_signals(features)
    assert signals == []
    assert calls["stage3"] == 0


def test_scalping_strategy_uses_5m_bias_and_1m_trigger(monkeypatch):
    now_utc = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)  # 10:00 NY
    strategy = ScalpingStrategy(_make_ctx(now_utc))

    idx = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2026-03-02T14:55:00Z"), "AAPL")],
        names=["datetime", "symbol"],
    )
    preds = pd.Series([0.01], index=idx)
    bars_df = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "datetime": [pd.Timestamp("2026-03-02T14:55:00Z")],
            "close": [100.0],
        }
    )

    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.scalping_strategy.stage3_qlib_score",
        lambda *a, **k: (preds, bars_df),
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
