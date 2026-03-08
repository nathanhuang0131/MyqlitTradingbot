from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Decision.models import DecisionInput, DecisionRecord
from qlib_tradingbot.Decision.policy import evaluate_decision


def _llm_payload(symbol: str, llm_bias_state: dict[str, Any]) -> dict[str, Any]:
    state = dict((llm_bias_state or {}).get(symbol.upper(), {}) or {})
    return {
        "bias": str(state.get("bias", "Neutral")),
        "prob": float(state.get("prob", 50.0) or 50.0),
        "action": str(state.get("action", "Hold")),
    }


def fuse_signals(
    signals: list[Signal],
    *,
    llm_bias_state: dict[str, Any],
    run_id: str,
    correlation_id: str,
    strategy_id: str,
    market_regime: str = "neutral",
    risk_state: dict[str, Any] | None = None,
) -> tuple[list[Signal], list[DecisionRecord]]:
    out_signals: list[Signal] = []
    traces: list[DecisionRecord] = []
    rs = dict(risk_state or {})

    for sig in signals:
        sym = str(sig.symbol).upper()
        llm = _llm_payload(sym, llm_bias_state)
        q_alpha = float(sig.features.get("alpha_total", sig.features.get("alpha", sig.score)) or 0.0)
        q_conf = float(sig.features.get("confidence", 0.5) or 0.5)
        q_rank = int(sig.features.get("rank", 0) or 0)
        q_model = str(sig.features.get("qlib_model_id", sig.features.get("model_id", "unknown")))
        q_h = str(sig.features.get("qlib_horizon", sig.features.get("horizon", "unknown")))
        inp = DecisionInput(
            symbol=sym,
            proposed_side=str(sig.side),
            qlib_alpha=q_alpha,
            qlib_confidence=q_conf,
            qlib_rank=q_rank,
            qlib_model_id=q_model,
            qlib_horizon=q_h,
            llm_bias=str(llm["bias"]),
            llm_probability=float(llm["prob"]),
            llm_action=str(llm["action"]),
            position_state=str(sig.features.get("position_state", "flat")),
            market_regime=str(market_regime),
            risk_state=rs,
        )
        decision = evaluate_decision(inp)
        traces.append(
            DecisionRecord(
                ts_utc=datetime.now(timezone.utc).isoformat(),
                run_id=run_id,
                correlation_id=sig.correlation_id or correlation_id,
                symbol=sym,
                strategy_id=strategy_id,
                model_id=q_model,
                qlib_alpha=q_alpha,
                qlib_confidence=q_conf,
                llm_bias=str(llm["bias"]),
                llm_probability=float(llm["prob"]),
                final_action=decision.final_action,
                blocked=decision.blocked,
                qlib_rank=q_rank,
                qlib_horizon=q_h,
                llm_action=str(llm["action"]),
                risk_state=rs,
                reasons=list(decision.reasons),
            )
        )
        if decision.final_action in {"buy", "sell", "reduce"}:
            new_side = "BUY" if decision.final_action == "buy" else "SELL"
            new_features = dict(sig.features or {})
            new_features.update(
                {
                    "fusion_action": decision.final_action,
                    "fusion_reasons": "|".join(decision.reasons),
                    "qlib_model_id": q_model,
                    "qlib_horizon": q_h,
                    "llm_bias": str(llm["bias"]),
                    "llm_probability": float(llm["prob"]),
                }
            )
            out_signals.append(replace(sig, side=new_side, features=new_features))
    return out_signals, traces
