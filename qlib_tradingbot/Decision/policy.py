from __future__ import annotations

from qlib_tradingbot.Decision.models import DecisionInput, DecisionOutput


def _norm(value: str) -> str:
    return str(value or "").strip().lower()


def evaluate_decision(inp: DecisionInput) -> DecisionOutput:
    reasons: list[str] = []
    side = _norm(inp.proposed_side)
    bias = _norm(inp.llm_bias)
    llm_prob = float(inp.llm_probability or 0.0)
    alpha = float(inp.qlib_alpha or 0.0)
    conf = float(inp.qlib_confidence or 0.0)
    risk_state = dict(inp.risk_state or {})

    if risk_state.get("blocked"):
        reasons.append("guardrail_blocked")
        return DecisionOutput(final_action="block", blocked=True, reasons=reasons, confidence=0.0)

    if conf < float(risk_state.get("min_qlib_confidence", 0.05)):
        reasons.append("low_qlib_confidence")
        return DecisionOutput(final_action="hold", blocked=False, reasons=reasons, confidence=conf)

    if side == "buy":
        if bias == "bearish" and llm_prob >= 70:
            reasons.append("llm_conflict_bearish_vs_buy")
            return DecisionOutput(final_action="block", blocked=True, reasons=reasons, confidence=conf)
        if alpha <= 0:
            reasons.append("non_positive_alpha_fallback_to_proposed_buy")
            return DecisionOutput(final_action="buy", blocked=False, reasons=reasons, confidence=conf)
        reasons.append("qlib_primary_buy")
        if bias == "bullish" and llm_prob >= 60:
            reasons.append("llm_confirmed_buy")
        return DecisionOutput(final_action="buy", blocked=False, reasons=reasons, confidence=conf)

    if side == "sell":
        if bias == "bullish" and llm_prob >= 75 and inp.position_state in {"long", "open_long"}:
            reasons.append("llm_conflict_bullish_vs_sell")
            return DecisionOutput(final_action="reduce", blocked=False, reasons=reasons, confidence=conf)
        reasons.append("qlib_primary_sell")
        return DecisionOutput(final_action="sell", blocked=False, reasons=reasons, confidence=conf)

    reasons.append("unsupported_side")
    return DecisionOutput(final_action="block", blocked=True, reasons=reasons, confidence=0.0)
