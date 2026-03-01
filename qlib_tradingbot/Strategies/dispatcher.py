from __future__ import annotations

from typing import Callable

from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext


class StrategyDispatcher:
    def __init__(self, factories: dict[str, Callable[[StrategyContext], StrategyBase]]):
        self._factories = {str(k).strip().lower(): v for k, v in factories.items()}

    def build(self, strategy_name: str, ctx: StrategyContext) -> StrategyBase:
        key = str(strategy_name).strip().lower()
        if key not in self._factories:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        return self._factories[key](ctx)

    def run(self, strategy_name: str, ctx: StrategyContext):
        strategy = self.build(strategy_name, ctx)
        universe = strategy.build_universe()
        features = strategy.prepare_features(universe)
        signals = strategy.generate_signals(features)
        execution_result = strategy.execute(signals)
        report = strategy.post_trade_reporting()
        return {
            "strategy": strategy.strategy_id,
            "universe_size": len(universe) if universe is not None else 0,
            "signals_size": len(signals) if signals is not None else 0,
            "execution_result": execution_result,
            "report": report,
        }
