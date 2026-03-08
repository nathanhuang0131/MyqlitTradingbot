from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Execution.engine import OrderResult, execute_signals
from qlib_tradingbot.Execution.guardrails import evaluate_execution_guardrails
from qlib_tradingbot.Execution.risk_manager import apply_signal_risk_controls
from qlib_tradingbot.Decision.fusion import fuse_signals
from qlib_tradingbot.LLM.feedback_handler import apply_feedback_gating, load_bias_state
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext
from qlib_tradingbot.Traceability.position_trace import (
    review_position_health,
    upsert_position_journal,
    write_decision_trace,
)


@dataclass(frozen=True)
class StrategyRunResult:
    strategy_id: str
    universe_size: int
    signals_size: int
    orders_size: int
    orders: list[OrderResult]


class StrategyRunner:
    """Run a strategy end-to-end in a deterministic, test-friendly flow."""

    def run_once(
        self,
        strategy: StrategyBase,
        ctx: StrategyContext,
        *,
        dry_run: bool = True,
        dry_run_output_dir: str | Path | None = None,
        allow_shorts: bool = True,
    ) -> StrategyRunResult:
        universe = strategy.build_universe() or []
        features = strategy.prepare_features(universe)
        signals_raw = strategy.generate_signals(features) or []
        signals = [s for s in signals_raw if isinstance(s, Signal)]

        bias_state = ctx.config.get("llm_bias_state", {}) if isinstance(ctx.config, dict) else {}
        if isinstance(bias_state, (str, Path)):
            bias_state = load_bias_state(bias_state)
        signals = apply_feedback_gating(
            signals,
            bias_state if isinstance(bias_state, dict) else {},
            prob_threshold=float((ctx.config or {}).get("llm_prob_threshold", 60.0)),
            neutral_size_factor=float((ctx.config or {}).get("llm_neutral_size_factor", 0.5)),
            default_dollars=float((ctx.config or {}).get("dollars_per_trade", 0.0)),
        )
        risked_signals, rejected = apply_signal_risk_controls(
            signals,
            max_dollars_per_trade=float((ctx.config or {}).get("dollars_per_trade", 250.0)),
            stop_loss_pct=float((ctx.config or {}).get("stop_loss_pct", 0.003)),
        )
        fused_signals, decision_records = fuse_signals(
            risked_signals,
            llm_bias_state=bias_state if isinstance(bias_state, dict) else {},
            run_id=str(ctx.run_id),
            correlation_id=str(ctx.correlation_id),
            strategy_id=str(getattr(strategy, "strategy_id", "unknown")),
            market_regime=str((ctx.config or {}).get("market_regime", "neutral")),
            risk_state={
                "blocked": bool((ctx.config or {}).get("risk_blocked", False)),
                "min_qlib_confidence": float((ctx.config or {}).get("min_qlib_confidence", 0.05)),
            },
        )
        data_root = Path(ctx.data_dir)
        try:
            write_decision_trace(data_root, decision_records)
            upsert_position_journal(
                data_root,
                decision_records,
                expected_horizon=str((ctx.config or {}).get("expected_horizon", "1D")),
                entry_thesis=str((ctx.config or {}).get("entry_thesis", "qlib-first + llm-governed decision")),
                target=float((ctx.config or {}).get("default_target_price", 0.0)),
                stop=float((ctx.config or {}).get("default_stop_price", 0.0)),
            )
            review_position_health(data_root)
        except Exception as exc:
            blocked = [
                OrderResult(
                    ok=False,
                    symbol=str(getattr(s, "symbol", "")),
                    action="BLOCK",
                    submitted=False,
                    error=f"trace_write_failed: {exc}",
                    correlation_id=str(getattr(s, "correlation_id", "")),
                )
                for s in fused_signals
            ]
            all_orders = [*rejected, *blocked]
            return StrategyRunResult(
                strategy_id=str(getattr(strategy, "strategy_id", "unknown")),
                universe_size=len(list(universe)),
                signals_size=len(fused_signals),
                orders_size=len(all_orders),
                orders=list(all_orders),
            )

        guard = evaluate_execution_guardrails(
            dry_run=bool(dry_run),
            trade_client=ctx.trade_client,
            signals_count=len(fused_signals),
            data_dir=data_root,
            cfg=ctx.config if isinstance(ctx.config, dict) else {},
        )
        if not guard.ok:
            blocked = [
                OrderResult(
                    ok=False,
                    symbol=str(getattr(s, "symbol", "")),
                    action="BLOCK",
                    submitted=False,
                    error=f"guardrail_blocked: {', '.join(guard.reasons)}",
                    correlation_id=str(getattr(s, "correlation_id", "")),
                )
                for s in fused_signals
            ]
            all_orders = [*rejected, *blocked]
            return StrategyRunResult(
                strategy_id=str(getattr(strategy, "strategy_id", "unknown")),
                universe_size=len(list(universe)),
                signals_size=len(fused_signals),
                orders_size=len(all_orders),
                orders=list(all_orders),
            )
        orders = execute_signals(
            ctx.trade_client,
            fused_signals,
            dry_run=bool(dry_run),
            dry_run_output_dir=dry_run_output_dir,
            allow_shorts=bool(allow_shorts),
        )
        all_orders = [*rejected, *orders]
        return StrategyRunResult(
            strategy_id=str(getattr(strategy, "strategy_id", "unknown")),
            universe_size=len(list(universe)),
            signals_size=len(risked_signals),
            orders_size=len(all_orders),
            orders=list(all_orders),
        )
