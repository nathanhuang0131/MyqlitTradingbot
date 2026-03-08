from __future__ import annotations

from qlib_tradingbot.Decision.models import DecisionInput
from qlib_tradingbot.Decision.policy import evaluate_decision


def test_fusion_blocks_buy_when_llm_strongly_bearish():
    inp = DecisionInput(
        symbol="AAPL",
        proposed_side="BUY",
        qlib_alpha=0.8,
        qlib_confidence=0.9,
        qlib_rank=1,
        qlib_model_id="qlib_model",
        qlib_horizon="1D",
        llm_bias="Bearish",
        llm_probability=92.0,
        llm_action="Exit",
        position_state="flat",
        market_regime="neutral",
        risk_state={"broker_ok": True},
    )
    out = evaluate_decision(inp)
    assert out.final_action == "block"
    assert any("llm_conflict" in r for r in out.reasons)


def test_fusion_prefers_buy_when_qlib_and_llm_align():
    inp = DecisionInput(
        symbol="MSFT",
        proposed_side="BUY",
        qlib_alpha=0.7,
        qlib_confidence=0.8,
        qlib_rank=2,
        qlib_model_id="qlib_model",
        qlib_horizon="1D",
        llm_bias="Bullish",
        llm_probability=85.0,
        llm_action="Add",
        position_state="flat",
        market_regime="risk_on",
        risk_state={"broker_ok": True},
    )
    out = evaluate_decision(inp)
    assert out.final_action == "buy"
    assert out.blocked is False

