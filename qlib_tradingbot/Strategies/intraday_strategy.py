from __future__ import annotations

from datetime import datetime, timezone

from qlib_tradingbot.Core.models import Signal
from qlib_tradingbot.Execution.engine import execute_signals
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext
from qlib_tradingbot.Strategies.position_model_strategies import _positions_set
from qlib_tradingbot.Utils.timezone_utils import to_new_york


class IntradayStrategy(StrategyBase):
    strategy_id = "intraday"

    def __init__(self, ctx: StrategyContext):
        self.ctx = ctx

    def build_universe(self):
        cfg = self.ctx.config or {}
        symbols = [str(s).upper() for s in cfg.get("universe_symbols", []) if str(s).strip()]
        positions = sorted(_positions_set(self.ctx.trade_client))
        return list(dict.fromkeys([*positions, *symbols]))

    def prepare_features(self, universe):
        return {"universe": universe, "held": _positions_set(self.ctx.trade_client)}

    def generate_signals(self, features):
        cfg = self.ctx.config or {}
        if not bool(cfg.get("force_eod_flat", True)):
            return []
        # Flatten near regular close boundary in NY time.
        ny_now = to_new_york(self.ctx.now_utc)
        if (ny_now.hour, ny_now.minute) < (15, 55):
            return []
        now_iso = datetime.now(timezone.utc).isoformat()
        return [
            Signal(
                symbol=sym,
                side="SELL",
                strategy_id=self.strategy_id,
                strategy_version="1.0",
                timeframe="1Day",
                reasons="intraday_eod_flatten",
                signal_ts_utc=now_iso,
            )
            for sym in sorted(features.get("held", set()))
        ]

    def execute(self, signals):
        if not signals or self.ctx.trade_client is None:
            return []
        return execute_signals(self.ctx.trade_client, signals)

    def post_trade_reporting(self):
        return {}
