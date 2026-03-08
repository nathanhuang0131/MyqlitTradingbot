from __future__ import annotations

from qlib_tradingbot.Decision.fusion import fuse_signals
from qlib_tradingbot.core.models import Signal


def _signal(**features: object) -> Signal:
    return Signal(
        symbol="AAPL",
        side="BUY",
        strategy_id="scalping",
        strategy_version="v1",
        timeframe="1Day",
        score=0.61,
        run_id="run1",
        correlation_id="corr1",
        features=dict(features),
    )


def test_fuse_signals_trace_contains_provenance_fields():
    out_signals, traces = fuse_signals(
        [_signal(alpha_total=0.7, confidence=0.82, rank=3, qlib_model_id="qlib_v2", qlib_horizon="3D")],
        llm_bias_state={"AAPL": {"bias": "Bullish", "prob": 88, "action": "Add"}},
        run_id="run1",
        correlation_id="corr_fallback",
        strategy_id="scalping",
        market_regime="risk_on",
        risk_state={"blocked": False, "min_qlib_confidence": 0.1},
    )

    assert len(out_signals) == 1
    assert len(traces) == 1
    rec = traces[0]
    assert rec.qlib_rank == 3
    assert rec.qlib_horizon == "3D"
    assert rec.llm_action == "Add"
    assert rec.risk_state.get("min_qlib_confidence") == 0.1


def test_fuse_signals_trace_defaults_when_optional_inputs_missing():
    _, traces = fuse_signals(
        [_signal()],
        llm_bias_state={},
        run_id="run1",
        correlation_id="corr_fallback",
        strategy_id="scalping",
    )

    rec = traces[0]
    assert rec.qlib_rank == 0
    assert rec.qlib_horizon == "unknown"
    assert rec.llm_action == "Hold"
    assert rec.risk_state == {}
