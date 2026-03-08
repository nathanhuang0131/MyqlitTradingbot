from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.ModelLifecycle.promotion import promote_if_eligible
from qlib_tradingbot.ModelLifecycle.registry import ModelCard, ModelRegistry
from qlib_tradingbot.ModelLifecycle.selector import select_best_model
from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.position_model_strategies import ShortTermStrategy
from qlib_tradingbot.Tools.backtest import run_backtest_from_csv


def test_gate_g_model_registry_writes_model_card(tmp_path: Path):
    registry = ModelRegistry(tmp_path / "model_registry")
    card = ModelCard(
        model_id="m1",
        strategy_id="short-term",
        metrics={"pnl_sum": 10.0, "win_rate": 0.6},
        params={"signal_threshold_buy": 0.01, "signal_threshold_sell": -0.01},
        artifact_path="Artifacts/m1.bin",
    )
    path = registry.register(card)
    assert path.is_file()
    loaded = registry.get("m1")
    assert loaded is not None
    assert loaded.metrics["win_rate"] == 0.6


def test_gate_h_backtest_command_deterministic_outputs(tmp_path: Path):
    root = Path(__file__).resolve().parent / "fixtures"
    bars = root / "backtest_bars.csv"
    sigs = root / "backtest_signals.csv"
    trades_path, summary_path = run_backtest_from_csv(
        bars_csv=bars,
        signals_csv=sigs,
        out_dir=tmp_path / "backtest_out",
        dollars_per_trade=100.0,
        horizon_bars=1,
    )
    assert trades_path.is_file()
    assert summary_path.is_file()
    trades = pd.read_csv(trades_path)
    summary = pd.read_csv(summary_path)
    assert len(trades) == 2
    assert float(summary.loc[0, "trades"]) == 2.0


def test_gate_i_model_selector_is_deterministic():
    cards = [
        ModelCard(model_id="m2", strategy_id="short-term", metrics={"pnl_sum": 5.0, "win_rate": 0.7}),
        ModelCard(model_id="m1", strategy_id="short-term", metrics={"pnl_sum": 5.0, "win_rate": 0.7}),
        ModelCard(model_id="m3", strategy_id="short-term", metrics={"pnl_sum": 4.0, "win_rate": 0.9}),
    ]
    best = select_best_model(cards)
    assert best is not None
    assert best.model_id == "m1"


def test_gate_j_promotion_updates_production_pointer(tmp_path: Path):
    registry = ModelRegistry(tmp_path / "model_registry")
    registry.register(ModelCard(model_id="bad", strategy_id="short-term", metrics={"pnl_sum": -1.0, "win_rate": 0.9}))
    registry.register(ModelCard(model_id="good", strategy_id="short-term", metrics={"pnl_sum": 10.0, "win_rate": 0.7}))

    assert promote_if_eligible(registry, "bad", min_win_rate=0.6, min_pnl_sum=0.0) is False
    assert promote_if_eligible(registry, "good", min_win_rate=0.6, min_pnl_sum=0.0) is True
    assert registry.get_production() == "good"


class _NoPosTradeClient:
    def get_all_positions(self):
        return []


def test_gate_k_selected_model_integrates_into_strategy_signals(monkeypatch, tmp_path: Path):
    registry = ModelRegistry(tmp_path / "model_registry")
    registry.register(
        ModelCard(
            model_id="prod-1",
            strategy_id="short-term",
            metrics={"pnl_sum": 11.0, "win_rate": 0.65},
            params={"signal_threshold_buy": 0.05, "signal_threshold_sell": -0.05},
        )
    )
    registry.set_production("prod-1")

    idx = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2026-03-02T14:55:00Z"), "AAPL")],
        names=["datetime", "symbol"],
    )
    preds = pd.Series([0.02], index=idx)
    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.position_model_strategies.stage3_qlib_score",
        lambda *a, **k: (preds, pd.DataFrame()),
    )

    ctx = StrategyContext(
        run_id="gate-k",
        correlation_id="gate-k",
        now_utc=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
        config={
            "universe_symbols": ["AAPL"],
            "max_positions": 5,
            "model_registry_dir": str(tmp_path / "model_registry"),
        },
        data_client=object(),
        trade_client=_NoPosTradeClient(),
    )
    strategy = ShortTermStrategy(ctx)
    features = strategy.prepare_features(["AAPL"])
    signals = strategy.generate_signals(features)
    assert signals == []
