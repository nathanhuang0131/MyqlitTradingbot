from __future__ import annotations

from typing import Callable

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext
from qlib_tradingbot.config import DRY_RUN as ENV_DRY_RUN


class StrategyDispatcher:
    def __init__(self, factories: dict[str, Callable[[StrategyContext], StrategyBase]]):
        self._factories = {str(k).strip().lower(): v for k, v in factories.items()}

    def build(self, strategy_name: str, ctx: StrategyContext) -> StrategyBase:
        key = str(strategy_name).strip().lower()
        if key not in self._factories:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        return self._factories[key](ctx)

    @staticmethod
    def _safe_monitor_log(ctx: StrategyContext, *, stage: str, status: str, message: str, metrics=None, sample_symbols=None, error=None):
        mon = getattr(ctx, "stage_monitor", None)
        if mon is None:
            return
        try:
            mon.log(
                stage=stage,
                status=status,
                message=message,
                metrics=metrics or {},
                sample_symbols=sample_symbols or [],
                error=error,
            )
        except Exception:
            return

    def run(self, strategy_name: str, ctx: StrategyContext):
        strategy = self.build(strategy_name, ctx)
        universe = strategy.build_universe()
        universe_list = [str(s).upper() for s in (universe or []) if str(s).strip()]
        self._safe_monitor_log(
            ctx,
            stage="stage1_universe",
            status="ok",
            message="universe built",
            metrics={"stage1_universe_size": len(universe_list)},
            sample_symbols=universe_list[:20],
        )
        features = strategy.prepare_features(universe)
        signals = strategy.generate_signals(features)
        signal_list = list(signals or [])
        buy_count = 0
        sell_count = 0
        sample_signal_symbols: list[str] = []
        for s in signal_list:
            side = ""
            symbol = ""
            if isinstance(s, Signal):
                side = str(s.side).upper()
                symbol = str(s.symbol).upper()
            elif hasattr(s, "side") or hasattr(s, "symbol"):
                side = str(getattr(s, "side", "")).upper()
                symbol = str(getattr(s, "symbol", "")).upper()
            elif isinstance(s, str):
                symbol = s.upper()
            if side == "BUY":
                buy_count += 1
            elif side == "SELL":
                sell_count += 1
            if symbol:
                sample_signal_symbols.append(symbol)
        self._safe_monitor_log(
            ctx,
            stage="stage3_signals",
            status="ok",
            message="signals generated",
            metrics={
                "signals_total": len(signal_list),
                "signals_buy": buy_count,
                "signals_sell": sell_count,
            },
            sample_symbols=sample_signal_symbols[:20],
        )
        execution_result = strategy.execute(signals)
        exec_list = list(execution_result or [])
        orders_submitted = sum(1 for x in exec_list if bool(getattr(x, "submitted", False)))
        orders_failed = sum(1 for x in exec_list if not bool(getattr(x, "ok", True)))
        self._safe_monitor_log(
            ctx,
            stage="stage3_execution",
            status="ok",
            message="execution completed",
            metrics={
                "dry_run": bool((ctx.config or {}).get("dry_run", ENV_DRY_RUN)),
                "orders_attempted": len(exec_list),
                "orders_submitted": int(orders_submitted),
                "orders_failed": int(orders_failed),
            },
        )
        report = strategy.post_trade_reporting()
        return {
            "strategy": strategy.strategy_id,
            "universe_size": len(universe) if universe is not None else 0,
            "signals_size": len(signals) if signals is not None else 0,
            "execution_result": execution_result,
            "report": report,
        }
