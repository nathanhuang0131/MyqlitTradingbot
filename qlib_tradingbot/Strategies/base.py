from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StrategyContext:
    run_id: str
    now_utc: datetime
    correlation_id: str = ""
    data_dir: str = "Data"
    config: dict[str, Any] = field(default_factory=dict)
    data_client: Any = None
    trade_client: Any = None


class StrategyBase:
    strategy_id: str = "base"

    def build_universe(self):
        raise NotImplementedError

    def prepare_features(self, universe):
        raise NotImplementedError

    def generate_signals(self, features):
        raise NotImplementedError

    def execute(self, signals):
        raise NotImplementedError

    def post_trade_reporting(self):
        raise NotImplementedError
