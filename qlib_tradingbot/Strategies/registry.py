from __future__ import annotations

from typing import Callable

from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext
from qlib_tradingbot.Strategies.intraday_strategy import IntradayStrategy
from qlib_tradingbot.Strategies.llm_planner_strategy import LLMPlannerStrategy
from qlib_tradingbot.Strategies.position_model_strategies import LongTermStrategy, ShortTermStrategy
from qlib_tradingbot.Strategies.scalping_strategy import ScalpingStrategy


StrategyFactory = Callable[[StrategyContext], StrategyBase]


class StrategyPluginRegistry:
    def __init__(self):
        self._factories: dict[str, StrategyFactory] = {}

    def register(self, name: str, factory: StrategyFactory) -> None:
        self._factories[str(name).strip().lower()] = factory

    def factories(self) -> dict[str, StrategyFactory]:
        return dict(self._factories)


def default_registry() -> StrategyPluginRegistry:
    reg = StrategyPluginRegistry()
    reg.register("scalping", lambda ctx: ScalpingStrategy(ctx))
    reg.register("intraday", lambda ctx: IntradayStrategy(ctx))
    reg.register("short-term", lambda ctx: ShortTermStrategy(ctx))
    reg.register("long-term", lambda ctx: LongTermStrategy(ctx))
    reg.register("llm-planner", lambda ctx: LLMPlannerStrategy(ctx))
    return reg
