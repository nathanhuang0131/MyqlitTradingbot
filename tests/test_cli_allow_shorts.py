from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.scalping_strategy import ScalpingStrategy
from qlib_tradingbot.UI.cli import build_runtime_config


def test_build_runtime_config_scalping_allow_shorts_default_false(monkeypatch):
    answers = iter(["", "", "", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    cfg = build_runtime_config("scalping")

    assert cfg["allow_shorts"] is False


def test_scalping_strategy_passes_allow_shorts_true(monkeypatch):
    captured = {"allow_shorts": None}

    def _fake_selection(_preds, _bars, **kwargs):
        captured["allow_shorts"] = kwargs.get("allow_shorts")
        return type("Sel", (), {"signals": [], "snapshot": pd.DataFrame()})()

    strategy = ScalpingStrategy(
        StrategyContext(
            run_id="r1",
            correlation_id="c1",
            now_utc=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
            config={
                "allow_shorts": True,
                "scalping_window_start_ny": "09:30",
                "scalping_window_end_ny": "11:00",
            },
            data_client=object(),
            trade_client=object(),
        )
    )

    monkeypatch.setattr("qlib_tradingbot.Strategies.scalping_strategy.signals_from_bias_and_1m_trigger", _fake_selection)

    strategy.generate_signals({"preds": pd.Series(dtype=float), "bars_1m": {}, "latest_close": {}})

    assert captured["allow_shorts"] is True
