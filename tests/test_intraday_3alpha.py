from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.Core.features_intraday import FEATURE_COLUMNS, build_intraday_features
from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.intraday_3alpha import Intraday3AlphaStrategy


def test_intraday_feature_builder_columns_and_label_fixture():
    fixture = Path(__file__).resolve().parent / "fixtures" / "intraday_ohlcv.csv"
    bars = pd.read_csv(fixture)
    out = build_intraday_features(bars)

    assert set(FEATURE_COLUMNS).issubset(set(out.columns))
    assert "label_fwd_ret_6" in out.columns

    i = 3
    close_i = float(bars.loc[i, "close"])
    close_fwd = float(bars.loc[i + 6, "close"])
    expected = close_fwd / close_i - 1.0
    assert abs(float(out.loc[i, "label_fwd_ret_6"]) - expected) < 1e-12


def test_intraday_alpha_blending_determinism(monkeypatch, tmp_path: Path):
    ctx = StrategyContext(
        run_id="r1",
        correlation_id="c1",
        now_utc=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        config={
            "universe_symbols": ["AAPL"],
            "w_alpha_ml": 0.55,
            "w_alpha_mr": 0.25,
            "w_alpha_mom": 0.20,
            "buy_threshold": -1.0,
            "sell_threshold": -2.0,
            "qlib_stub_mode": True,
        },
    )
    strategy = Intraday3AlphaStrategy(ctx)

    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.intraday_3alpha.QlibSignalEngine.run",
        lambda *a, **k: pd.DataFrame([
            {
                "symbol": "AAPL",
                "timestamp": "2026-03-02T15:00:00Z",
                "alpha": 0.2,
                "direction": "BUY",
                "confidence": 0.2,
                "horizon": "30m",
                "model_id": "m1",
            }
        ]),
    )

    feats = pd.DataFrame([
        {
            "symbol": "AAPL",
            "ret_6": 0.01,
            "vwap_dist": -0.01,
            "bb_z": -1.0,
            "rsi_14": 35.0,
            "alpha_mom": 0.3,
            "close_last": 100.0,
        }
    ])
    sigs = strategy.generate_signals({"feature_frame": feats})
    assert len(sigs) == 1

    f = sigs[0].features
    expected = 0.55 * f["alpha_ml"] + 0.25 * f["alpha_mr"] + 0.20 * f["alpha_mom"]
    assert abs(float(f["alpha_total"]) - expected) < 1e-12


def test_intraday_3alpha_uses_qlib_signal_engine_ranking(monkeypatch, tmp_path: Path):
    ctx = StrategyContext(
        run_id="r2",
        correlation_id="c2",
        now_utc=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        config={"universe_symbols": ["AAPL", "MSFT"], "buy_threshold": -1.0, "sell_threshold": -2.0},
    )
    strategy = Intraday3AlphaStrategy(ctx)

    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.intraday_3alpha.QlibSignalEngine.run",
        lambda *a, **k: pd.DataFrame([
            {"symbol": "MSFT", "timestamp": "2026-03-02T15:00:00Z", "alpha": 0.9, "direction": "BUY", "confidence": 0.9, "horizon": "30m", "model_id": "m"},
            {"symbol": "AAPL", "timestamp": "2026-03-02T15:00:00Z", "alpha": 0.1, "direction": "BUY", "confidence": 0.1, "horizon": "30m", "model_id": "m"},
        ]),
    )

    feats = pd.DataFrame([
        {"symbol": "AAPL", "vwap_dist": 0.0, "bb_z": 0.0, "rsi_14": 50.0, "alpha_mom": 0.0, "close_last": 100.0},
        {"symbol": "MSFT", "vwap_dist": 0.0, "bb_z": 0.0, "rsi_14": 50.0, "alpha_mom": 0.0, "close_last": 100.0},
    ])
    sigs = strategy.generate_signals({"feature_frame": feats})
    assert [s.symbol for s in sigs][:2] == ["MSFT", "AAPL"]


def test_intraday_runner_dry_run_one_shot_outputs(tmp_path: Path):
    data_dir = tmp_path / "Data"
    (data_dir / "llm_feedback").mkdir(parents=True, exist_ok=True)
    (data_dir / "llm_feedback" / "llm_bias_state.json").write_text("{}", encoding="utf-8")

    cmd = [
        sys.executable,
        "-m",
        "qlib_tradingbot.apps.cli_app",
        "--strategy",
        "intraday_3alpha",
        "--mode",
        "loop",
        "--max-iter",
        "1",
        "--rebalance-min",
        "15",
        "--ny-window",
        "00:00-23:59",
        "--paper",
        "--data-dir",
        str(data_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr

    assert (data_dir / "signals" / "intraday_3alpha_signals.csv").exists()
    assert (data_dir / "intents" / "intents.csv").exists()
    assert (data_dir / "trade_history" / "mock_orders.csv").exists()
    assert (data_dir / "trades_ledger.csv").exists()


def test_intraday_llm_bias_bearish_reduces_longs(tmp_path: Path):
    state_dir = tmp_path / "llm_feedback"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "llm_bias_state.json").write_text('{"AAPL": {"bias": "Bearish", "prob": 95}}', encoding="utf-8")

    ctx = StrategyContext(
        run_id="r3",
        correlation_id="c3",
        now_utc=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
        data_dir=str(tmp_path),
        config={
            "buy_threshold": 0.05,
            "sell_threshold": -0.05,
            "llm_prob_threshold": 70.0,
            "llm_bias_state_path": str(state_dir / "llm_bias_state.json"),
            "universe_symbols": ["AAPL"],
        },
    )
    strategy = Intraday3AlphaStrategy(ctx)

    feats = pd.DataFrame([
        {"symbol": "AAPL", "vwap_dist": 0.0, "bb_z": 0.0, "rsi_14": 50.0, "alpha_mom": 0.0, "close_last": 100.0}
    ])
    strategy_output = pd.DataFrame([
        {"symbol": "AAPL", "timestamp": "2026-03-02T15:00:00Z", "alpha": 0.051, "direction": "BUY", "confidence": 0.9, "horizon": "30m", "model_id": "m"}
    ])

    # Without bias adjustment, this would pass buy threshold; bearish bias makes it stricter.
    from qlib_tradingbot.Strategies import intraday_3alpha as mod

    original = mod.QlibSignalEngine.run
    mod.QlibSignalEngine.run = lambda *a, **k: strategy_output
    try:
        sigs = strategy.generate_signals({"feature_frame": feats})
    finally:
        mod.QlibSignalEngine.run = original

    assert sigs == []
