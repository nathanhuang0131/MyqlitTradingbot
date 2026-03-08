from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext


class LLMPlannerStrategy(StrategyBase):
    strategy_id = "llm-planner"

    def __init__(self, ctx: StrategyContext):
        self.ctx = ctx

    def build_universe(self):
        symbols = [str(s).upper() for s in self.ctx.config.get("universe_symbols", []) if str(s).strip()]
        return symbols

    def prepare_features(self, universe):
        prompt_path = self.ctx.config.get("llm_prompt_path", "")
        template = ""
        if prompt_path:
            p = Path(prompt_path)
            if p.exists():
                template = p.read_text(encoding="utf-8")
        return {"universe": universe, "template": template}

    def generate_signals(self, features):
        universe = list(features.get("universe", []))
        template = str(features.get("template", "")).upper()
        now_iso = datetime.now(timezone.utc).isoformat()

        out = []
        for i, sym in enumerate(universe):
            side = "BUY"
            if "HOLD" in template and i % 2 == 1:
                side = "SELL"
            out.append(
                Signal(
                    symbol=str(sym).upper(),
                    side=side,  # deterministic stub recommendation
                    strategy_id=self.strategy_id,
                    strategy_version="stub-v1",
                    timeframe="1Day",
                    reasons="deterministic_template_stub",
                    signal_ts_utc=now_iso,
                )
            )
        return out

    def execute(self, signals):
        return []

    def post_trade_reporting(self):
        return {}
