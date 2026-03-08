from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DecisionAction = Literal["buy", "sell", "reduce", "hold", "block"]


@dataclass(frozen=True)
class DecisionInput:
    symbol: str
    proposed_side: str
    qlib_alpha: float
    qlib_confidence: float
    qlib_rank: int
    qlib_model_id: str
    qlib_horizon: str
    llm_bias: str
    llm_probability: float
    llm_action: str
    position_state: str
    market_regime: str
    risk_state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionOutput:
    final_action: DecisionAction
    blocked: bool
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass(frozen=True)
class DecisionRecord:
    ts_utc: str
    run_id: str
    correlation_id: str
    symbol: str
    strategy_id: str
    model_id: str
    qlib_alpha: float
    qlib_confidence: float
    llm_bias: str
    llm_probability: float
    final_action: str
    blocked: bool
    qlib_rank: int = 0
    qlib_horizon: str = "unknown"
    llm_action: str = "Hold"
    risk_state: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
