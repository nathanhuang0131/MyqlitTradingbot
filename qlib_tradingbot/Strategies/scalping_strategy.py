from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.core.qlib_signal_engine import QlibSignalEngine, SignalEngineConfig
from qlib_tradingbot.Data.batch_bars import BatchFetchConfig, fetch_1m_bars_batch
from qlib_tradingbot.Execution.engine import execute_signals
from qlib_tradingbot.Execution.shorting import preflight_allow_shorts
from qlib_tradingbot.LLM.feedback_handler import apply_feedback_gating, refresh_bias_state
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext
from qlib_tradingbot.Strategies.hybrid_bias_trigger import signals_from_bias_and_1m_trigger
from qlib_tradingbot.Strategies.scalp_pipeline_qlib import (
    PipelineConfig,
    run_3stage_qlib_scalp_pipeline,
)
from qlib_tradingbot.Utils.timezone_utils import in_ny_trading_window
from qlib_tradingbot.config import DRY_RUN


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

    def _monitor_log(self, *, stage: str, status: str, message: str, metrics=None, sample_symbols=None, error=None) -> None:
        mon = getattr(self.ctx, "stage_monitor", None)
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

    def build_universe(self):
        cfg = PipelineConfig()
        out_dir = Path(self.ctx.data_dir)
        if self.ctx.data_client is None or self.ctx.trade_client is None:
            self._monitor_log(
                stage="stage1_alpaca_fetch",
                status="fail",
                message="missing clients for scalping pipeline",
                metrics={"fetch_ok": False, "symbols_returned_total": 0, "duration_ms": 0},
            )
            return []
        run_3stage_qlib_scalp_pipeline(
            data_client=self.ctx.data_client,
            trade_client=self.ctx.trade_client,
            run_id=self.ctx.run_id,
            correlation_id=self.ctx.correlation_id or self.ctx.run_id,
            cfg=cfg,
            output_dir=str(out_dir),
            stage_monitor=self.ctx.stage_monitor,
        )
        universe_path = out_dir / "universe_trade_today.csv"
        if not universe_path.exists():
            self._monitor_log(
                stage="stage3_monitor_universe",
                status="ok",
                message="trade universe file missing",
                metrics={"final_universe_size": 0},
            )
            return []
        df = pd.read_csv(universe_path)
        col = "Symbol" if "Symbol" in df.columns else "symbol"
        if col not in df.columns:
            self._monitor_log(
                stage="stage3_monitor_universe",
                status="ok",
                message="trade universe column missing",
                metrics={"final_universe_size": 0},
            )
            return []
        universe = [str(x).strip().upper() for x in df[col].dropna().tolist() if str(x).strip()]
        self._monitor_log(
            stage="stage3_monitor_universe",
            status="ok",
            message="scalping trade universe ready",
            metrics={"final_universe_size": int(len(universe))},
            sample_symbols=universe[:20],
        )
        return universe

    def prepare_features(self, universe):
        if not universe:
            self._monitor_log(
                stage="stage3_data_fetch",
                status="skipped",
                message="no symbols in monitor universe",
                metrics={"bars_requested_symbols": 0, "bars_received_symbols": 0, "bars_missing_symbols_count": 0, "duration_ms": 0},
            )
            return {"universe": list(universe or []), "preds": pd.Series(dtype=float), "bars_1m": {}, "latest_close": {}}
        if not self._active():
            self._monitor_log(
                stage="stage3_data_fetch",
                status="skipped",
                message="outside scalping window",
                metrics={"bars_requested_symbols": int(len(universe)), "bars_received_symbols": 0, "bars_missing_symbols_count": int(len(universe)), "duration_ms": 0},
            )
            return {"universe": list(universe or []), "preds": pd.Series(dtype=float), "bars_1m": {}, "latest_close": {}}

        engine = QlibSignalEngine(
            data_root=Path(self.ctx.data_dir),
            config=SignalEngineConfig(
                model_id=str(self.ctx.config.get("qlib_model_id", "qlib_stub_v1")),
                horizon=str(self.ctx.config.get("qlib_horizon", "1D")),
            ),
        )
        qlib_frame = engine.run(universe, stub=bool(self.ctx.config.get("qlib_stub_mode", False)))
        ranked_universe = qlib_frame["symbol"].astype(str).str.upper().tolist() if not qlib_frame.empty else list(universe or [])

        t0 = perf_counter()
        bars_1m = fetch_1m_bars_batch(
            self.ctx.data_client,
            symbols=ranked_universe,
            lookback_days=int(self.ctx.config.get("lookback_days_1m", 2)),
            cfg=BatchFetchConfig(),
        )
        duration_ms = int((perf_counter() - t0) * 1000)
        bars_received_symbols = sum(
            1
            for _sym, df in (bars_1m or {}).items()
            if isinstance(df, pd.DataFrame) and not df.empty
        )
        self._monitor_log(
            stage="stage3_data_fetch",
            status="ok",
            message="1m bars fetched for trigger checks",
            metrics={
                "bars_requested_symbols": int(len(universe)),
                "bars_received_symbols": int(bars_received_symbols),
                "bars_missing_symbols_count": int(max(0, len(universe) - bars_received_symbols)),
                "duration_ms": int(duration_ms),
            },
        )
        latest_close: dict[str, float] = {}
        for sym, bdf in (bars_1m or {}).items():
            if isinstance(bdf, pd.DataFrame) and not bdf.empty and "close" in bdf.columns:
                try:
                    latest_close[str(sym).upper()] = float(pd.to_numeric(bdf["close"], errors="coerce").dropna().iloc[-1])
                except Exception:
                    continue

        preds = pd.Series(dtype=float)
        if not qlib_frame.empty:
            ts = pd.to_datetime(qlib_frame["timestamp"], utc=True, errors="coerce").fillna(pd.Timestamp.now(tz="UTC"))
            idx = pd.MultiIndex.from_arrays(
                [ts, qlib_frame["symbol"].astype(str).str.upper()],
                names=["datetime", "symbol"],
            )
            preds = pd.Series(pd.to_numeric(qlib_frame["alpha"], errors="coerce").fillna(0.0).values, index=idx)

        return {
            "universe": ranked_universe,
            "preds": preds,
            "bars_1m": bars_1m,
            "latest_close": latest_close,
            "qlib_signal_frame": qlib_frame,
        }

    def generate_signals(self, features):
        if not self._active():
            self._monitor_log(
                stage="stage3_signals",
                status="skipped",
                message="outside scalping window",
                metrics={"signals_total": 0, "signals_buy": 0, "signals_sell": 0},
            )
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
        gated = apply_feedback_gating(
            selection.signals,
            state,
            prob_threshold=float(self.ctx.config.get("llm_prob_threshold", 60.0)),
            neutral_size_factor=float(self.ctx.config.get("llm_neutral_size_factor", 0.5)),
            default_dollars=float(self.ctx.config.get("dollars_per_trade", 0.0)),
        )
        buy_count = sum(1 for s in gated if str(getattr(s, "side", "")).upper() == "BUY")
        sell_count = sum(1 for s in gated if str(getattr(s, "side", "")).upper() == "SELL")
        self._monitor_log(
            stage="stage3_signals",
            status="ok",
            message="signals generated after feedback gating",
            metrics={"signals_total": int(len(gated)), "signals_buy": int(buy_count), "signals_sell": int(sell_count)},
            sample_symbols=[str(getattr(s, "symbol", "")).upper() for s in gated[:20] if str(getattr(s, "symbol", "")).strip()],
        )
        return gated

    def execute(self, signals):
        effective_dry_run = bool((self.ctx.config or {}).get("dry_run", DRY_RUN))
        if not signals:
            self._monitor_log(
                stage="stage3_execution",
                status="ok",
                message="no signals to execute",
                metrics={
                    "dry_run": bool(effective_dry_run),
                    "orders_attempted": 0,
                    "orders_submitted": 0,
                    "orders_failed": 0,
                    "brackets_attempted": 0,
                    "brackets_submitted": 0,
                    "brackets_downgraded_to_simple": 0,
                    "simple_notional_submitted": 0,
                    "rejection_reasons": {},
                },
            )
            return []
        if self.ctx.trade_client is None:
            self._monitor_log(
                stage="stage3_execution",
                status="fail",
                message="missing trade client",
                metrics={
                    "dry_run": bool(effective_dry_run),
                    "orders_attempted": int(len(signals)),
                    "orders_submitted": 0,
                    "orders_failed": int(len(signals)),
                    "brackets_attempted": 0,
                    "brackets_submitted": 0,
                    "brackets_downgraded_to_simple": 0,
                    "simple_notional_submitted": 0,
                    "rejection_reasons": {"missing_trade_client": int(len(signals))},
                },
            )
            return []
        allow_shorts = preflight_allow_shorts(
            self.ctx.trade_client,
            bool(self.ctx.config.get("allow_shorts", False)),
        )
        if isinstance(signals[0], Signal):
            results = execute_signals(
                self.ctx.trade_client,
                signals,
                dry_run=effective_dry_run,
                allow_shorts=allow_shorts,
            )
        else:
            results = signals

        orders_attempted = int(len(results or []))
        orders_submitted = sum(1 for r in (results or []) if bool(getattr(r, "submitted", False)))
        orders_failed = sum(1 for r in (results or []) if not bool(getattr(r, "ok", True)))
        bracket_actions = {
            "BRACKET_BUY",
            "BRACKET_SHORT",
            "BRACKET_MARKET",
            "BRACKET_BUY",
            "BRACKET_SELL_SHORT",
        }
        brackets_attempted = 0
        brackets_submitted = 0
        brackets_downgraded_to_simple = 0
        simple_notional_submitted = 0
        rejection_reasons: dict[str, int] = {}
        for r in (results or []):
            action = str(getattr(r, "action", "")).upper()
            err = str(getattr(r, "error", "") or "").strip()
            if action in bracket_actions:
                brackets_attempted += 1
                if bool(getattr(r, "submitted", False)) and bool(getattr(r, "ok", True)):
                    brackets_submitted += 1
            if action == "SIMPLE_NOTIONAL_BUY_FALLBACK":
                brackets_downgraded_to_simple += 1
                if bool(getattr(r, "submitted", False)):
                    simple_notional_submitted += 1
            if err:
                rejection_reasons[err] = rejection_reasons.get(err, 0) + 1

        self._monitor_log(
            stage="stage3_execution",
            status="ok",
            message="execution completed",
            metrics={
                "dry_run": bool(effective_dry_run),
                "orders_attempted": int(orders_attempted),
                "orders_submitted": int(orders_submitted),
                "orders_failed": int(orders_failed),
                "brackets_attempted": int(brackets_attempted),
                "brackets_submitted": int(brackets_submitted),
                "brackets_downgraded_to_simple": int(brackets_downgraded_to_simple),
                "simple_notional_submitted": int(simple_notional_submitted),
                "rejection_reasons": rejection_reasons,
            },
        )
        return results

    def post_trade_reporting(self):
        return {"signals_snapshot_rows": int(len(self._latest_snapshot))}
