from __future__ import annotations

from pathlib import Path

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.LLM.feedback_handler import apply_feedback_gating, parse_feedback_text, refresh_bias_state


def test_parse_feedback_text_with_minor_format_noise():
    text = (
        "SYMBOL: AAPL\n"
        "BIAS: Bullish\n"
        "PROB: 70\n"
        "ACTION: Hold\n\n"
        "SYMBOL: TSLA\n"
        "BIAS Bearish\n"  # malformed, should fall back to neutral defaults if missing key
        "PROB: 55\n"
        "ACTION: Exit\n"
    )
    parsed = parse_feedback_text(text)

    assert parsed["AAPL"]["bias"] == "Bullish"
    assert parsed["AAPL"]["prob"] == 70.0
    assert parsed["TSLA"]["prob"] == 55.0
    assert parsed["TSLA"]["bias"] == "Neutral"


def test_feedback_gating_skip_and_resize_rules():
    signals = [
        Signal(symbol="AAPL", side="BUY", strategy_id="S", strategy_version="1", timeframe="1Min", features={}),
        Signal(symbol="TSLA", side="BUY", strategy_id="S", strategy_version="1", timeframe="1Min", features={}),
        Signal(symbol="NVDA", side="BUY", strategy_id="S", strategy_version="1", timeframe="1Min", features={}),
    ]
    state = {
        "AAPL": {"bias": "Bearish", "prob": 90, "action": "Exit"},
        "TSLA": {"bias": "Bullish", "prob": 40, "action": "Hold"},
        "NVDA": {"bias": "Neutral", "prob": 80, "action": "Hold"},
    }

    out = apply_feedback_gating(signals, state, prob_threshold=60, neutral_size_factor=0.5, default_dollars=200)

    assert len(out) == 1
    assert out[0].symbol == "NVDA"
    assert float(out[0].features.get("dollars", 0)) == 100.0


def test_refresh_bias_state_writes_json_from_feedback(tmp_path: Path):
    feedback = tmp_path / "llm_feedback_latest.txt"
    feedback.write_text(
        "SYMBOL: AAPL\nBIAS: Bullish\nPROB: 80\nACTION: Add\n",
        encoding="utf-8",
    )

    state = refresh_bias_state(tmp_path)

    assert (tmp_path / "llm_bias_state.json").exists()
    assert "AAPL" in state
