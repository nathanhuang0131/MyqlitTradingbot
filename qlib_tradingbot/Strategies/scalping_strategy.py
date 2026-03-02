from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from qlib_tradingbot.Core.models import Signal
from qlib_tradingbot.Data.batch_bars import BatchFetchConfig, fetch_1m_bars_batch
from qlib_tradingbot.Execution.engine import execute_signals
from qlib_tradingbot.Execution.shorting import preflight_allow_shorts
from qlib_tradingbot.LLM.feedback_handler import apply_feedback_gating, refresh_bias_state
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext
from qlib_tradingbot.Strategies.hybrid_bias_trigger import signals_from_bias_and_1m_trigger
from qlib_tradingbot.Strategies.scalp_pipeline_qlib import (
    PipelineConfig,
    Stage3Config,
    run_3stage_qlib_scalp_pipeline,
    stage3_qlib_score,
)
from qlib_tradingbot.Utils.timezone_utils import in_ny_trading_window


class ScalpingStrategy(StrategyBase):
    strategy_id = "scalping"

    def __init__(self, ctx: StrategyContext):
        self.ctx = ctx
        self._latest_snapshot = pd.DataFrame()

    def _window(self) -> tuple[str, str]:
        cfg = self.ctx.config or {}
        return (
            str(cfg.get("scalping_window_start_ny", "09:30")),
            str(cfg.get("scalping_window_end_ny", "11:00")),
        )

    def _active(self) -> bool:
        start_hhmm, end_hhmm = self._window()
        return in_ny_trading_window(self.ctx.now_utc, start_hhmm, end_hhmm)

    def build_universe(self):
        cfg = PipelineConfig()
        out_dir = Path(self.ctx.data_dir)
        if self.ctx.data_client is None or self.ctx.trade_client is None:
            return []
        run_3stage_qlib_scalp_pipeline(
            data_client=self.ctx.data_client,
            trade_client=self.ctx.trade_client,
            run_id=self.ctx.run_id,
            correlation_id=self.ctx.correlation_id or self.ctx.run_id,
            cfg=cfg,
            output_dir=str(out_dir),
        )
        universe_path = out_dir / "universe_trade_today.csv"
        if not universe_path.exists():
            return []
        df = pd.read_csv(universe_path)
        col = "Symbol" if "Symbol" in df.columns else "symbol"
        if col not in df.columns:
            return []
        return [str(x).strip().upper() for x in df[col].dropna().tolist() if str(x).strip()]

    def prepare_features(self, universe):
        if not universe or not self._active():
            return {"universe": list(universe or []), "preds": pd.Series(dtype=float), "bars_1m": {}, "latest_close": {}}

        preds, bars_df = stage3_qlib_score(
            self.ctx.data_client,
            symbols=universe,
            batch_cfg=BatchFetchConfig(),
            lookback_days_5m=int(self.ctx.config.get("lookback_days_5m", 14)),
            cfg=Stage3Config(top_n_signals=int(self.ctx.config.get("top_n_signals", 30))),
        )

        latest_close = {}
        if bars_df is not None and not bars_df.empty and {"symbol", "datetime", "close"}.issubset(set(bars_df.columns)):
            latest_close = (
                bars_df.sort_values(["symbol", "datetime"])
                .groupby("symbol")["close"]
                .last()
                .astype(float)
                .to_dict()
            )

        bars_1m = fetch_1m_bars_batch(
            self.ctx.data_client,
            symbols=universe,
            lookback_days=int(self.ctx.config.get("lookback_days_1m", 2)),
            cfg=BatchFetchConfig(),
        )
        return {"universe": universe, "preds": preds, "bars_1m": bars_1m, "latest_close": latest_close}

    def generate_signals(self, features):
        if not self._active():
            return []
        selection = signals_from_bias_and_1m_trigger(
            features.get("preds", pd.Series(dtype=float)),
            features.get("bars_1m", {}),
            top_n=int(self.ctx.config.get("top_n_signals", 30)),
            allow_shorts=bool(self.ctx.config.get("allow_shorts", False)),
            price_basis_by_symbol=features.get("latest_close", {}),
        )
        self._latest_snapshot = selection.snapshot if selection.snapshot is not None else pd.DataFrame()
        state = refresh_bias_state(self.ctx.data_dir)
        return apply_feedback_gating(
            selection.signals,
            state,
            prob_threshold=float(self.ctx.config.get("llm_prob_threshold", 60.0)),
            neutral_size_factor=float(self.ctx.config.get("llm_neutral_size_factor", 0.5)),
            default_dollars=float(self.ctx.config.get("dollars_per_trade", 0.0)),
        )

    def execute(self, signals):
        if not signals:
            return []
        if self.ctx.trade_client is None:
            return []
        allow_shorts = preflight_allow_shorts(
            self.ctx.trade_client,
            bool(self.ctx.config.get("allow_shorts", False)),
        )
        if isinstance(signals[0], Signal):
            return execute_signals(self.ctx.trade_client, signals, allow_shorts=allow_shorts)
        return signals

    def post_trade_reporting(self):
        return {"signals_snapshot_rows": int(len(self._latest_snapshot))}
