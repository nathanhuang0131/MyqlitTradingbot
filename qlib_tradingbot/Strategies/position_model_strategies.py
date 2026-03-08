from __future__ import annotations

from datetime import timezone, datetime
from typing import Iterable

import pandas as pd

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Data.batch_bars import BatchFetchConfig
from qlib_tradingbot.Execution.engine import execute_signals
from qlib_tradingbot.ModelLifecycle.integration import load_selected_model_thresholds
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext
from qlib_tradingbot.Strategies.scalp_pipeline_qlib import Stage3Config, stage3_qlib_score


def _latest_preds(preds: pd.Series) -> pd.Series:
    if preds is None or len(preds) == 0:
        return pd.Series(dtype=float)
    if not isinstance(preds.index, pd.MultiIndex):
        return pd.Series(dtype=float)
    latest_dt = preds.index.get_level_values(0).max()
    latest = preds.xs(latest_dt, level=0).dropna()
    latest.index = latest.index.astype(str).str.upper()
    return latest.sort_values(ascending=False)


def _positions_set(trade_client) -> set[str]:
    if trade_client is None:
        return set()
    try:
        return {str(getattr(p, "symbol", "")).upper() for p in (trade_client.get_all_positions() or []) if str(getattr(p, "symbol", "")).strip()}
    except Exception:
        return set()


class _PositionModelStrategyBase(StrategyBase):
    strategy_id = "position-model"
    threshold_buy = 0.002
    threshold_sell = -0.002

    def __init__(self, ctx: StrategyContext):
        self.ctx = ctx

    def build_universe(self):
        cfg = self.ctx.config or {}
        symbols = [str(s).upper() for s in cfg.get("universe_symbols", []) if str(s).strip()]
        positions = sorted(_positions_set(self.ctx.trade_client))
        return list(dict.fromkeys([*positions, *symbols]))

    def prepare_features(self, universe):
        if not universe:
            return {"preds": pd.Series(dtype=float), "held": set(), "selected_thresholds": (None, None)}
        preds, _ = stage3_qlib_score(
            self.ctx.data_client,
            symbols=universe,
            batch_cfg=BatchFetchConfig(),
            lookback_days_5m=int(self.ctx.config.get("lookback_days_model", 20)),
            cfg=Stage3Config(top_n_signals=int(self.ctx.config.get("top_n_signals", 10))),
        )
        registry_dir = self.ctx.config.get("model_registry_dir", "Data/model_registry")
        selected_thresholds = load_selected_model_thresholds(registry_dir)
        return {"preds": _latest_preds(preds), "held": _positions_set(self.ctx.trade_client), "selected_thresholds": selected_thresholds}

    def generate_signals(self, features):
        preds: pd.Series = features.get("preds", pd.Series(dtype=float))
        held: set[str] = features.get("held", set())
        selected_buy, selected_sell = features.get("selected_thresholds", (None, None))
        threshold_buy = float(selected_buy) if selected_buy is not None else float(self.threshold_buy)
        threshold_sell = float(selected_sell) if selected_sell is not None else float(self.threshold_sell)
        if preds.empty:
            return []

        now_iso = datetime.now(timezone.utc).isoformat()
        signals: list[Signal] = []
        max_positions = int(self.ctx.config.get("max_positions", 5))
        slots = max(0, max_positions - len(held))

        for sym in held:
            score = float(preds.get(sym, 0.0))
            if score <= threshold_sell:
                signals.append(
                    Signal(
                        symbol=sym,
                        side="SELL",
                        strategy_id=self.strategy_id,
                        strategy_version="1.0",
                        timeframe="1Day",
                        score=score,
                        reasons=f"score {score:.6f} <= sell threshold {threshold_sell}",
                        signal_ts_utc=now_iso,
                    )
                )

        if slots <= 0:
            return signals

        for sym, score in preds.items():
            if sym in held:
                continue
            if float(score) >= threshold_buy:
                signals.append(
                    Signal(
                        symbol=str(sym),
                        side="BUY",
                        strategy_id=self.strategy_id,
                        strategy_version="1.0",
                        timeframe="1Day",
                        score=float(score),
                        reasons=f"score {float(score):.6f} >= buy threshold {threshold_buy}",
                        signal_ts_utc=now_iso,
                    )
                )
                slots -= 1
                if slots <= 0:
                    break
        return signals

    def execute(self, signals):
        if not signals or self.ctx.trade_client is None:
            return []
        return execute_signals(self.ctx.trade_client, signals)

    def post_trade_reporting(self):
        return {}


class ShortTermStrategy(_PositionModelStrategyBase):
    strategy_id = "short-term"
    threshold_buy = 0.001
    threshold_sell = -0.001


class LongTermStrategy(_PositionModelStrategyBase):
    strategy_id = "long-term"
    threshold_buy = 0.003
    threshold_sell = -0.003
