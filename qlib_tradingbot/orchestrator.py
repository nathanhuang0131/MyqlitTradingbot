from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qlib_tradingbot.Brokers.alpaca_gateway import get_market_clock, get_positions
from qlib_tradingbot.Analytics.ledger import append_execution_results_ledger
from qlib_tradingbot.core.stage_monitor import StageMonitor
from qlib_tradingbot.Reporting.reporting import (
    now_ny_iso,
    write_orders_csv,
    write_positions_csv,
    write_run_log,
    write_signals_csv,
)
from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher
from qlib_tradingbot.Utils.timezone_utils import in_ny_trading_window
from qlib_tradingbot.config import DRY_RUN as ENV_DRY_RUN


class Orchestrator:
    def __init__(self, dispatcher: StrategyDispatcher):
        self.dispatcher = dispatcher

    def _market_open_or_skip(self, ctx: StrategyContext) -> bool:
        clk = get_market_clock(ctx.trade_client)
        return bool(clk.is_open)

    @staticmethod
    def _safe_monitor_log(ctx: StrategyContext, *, stage: str, status: str, message: str, metrics=None, sample_symbols=None, error=None) -> None:
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

    @staticmethod
    def _build_execution_summary(summary: dict[str, Any], *, strategy_name: str, loop_sleep_sec: int, trace_csv: Path) -> dict[str, Any]:
        latest = summary.get("latest_by_stage", {}) or {}
        gate = latest.get("stage0_gate", {})
        stage1 = latest.get("stage1_universe", {})
        stage2 = latest.get("stage2_filters", {})
        stage3u = latest.get("stage3_monitor_universe", {})
        sigs = latest.get("stage3_signals", {})
        exe = latest.get("stage3_execution", {})

        stage2_metrics = dict(stage2.get("metrics", {}) or {})
        filters_breakdown = dict(stage2_metrics.get("filters_breakdown", {}) or {})
        top_filter = ""
        top_removed = -1
        for fname, vals in filters_breakdown.items():
            removed = int((vals or {}).get("removed", 0))
            if removed > top_removed:
                top_removed = removed
                top_filter = str(fname)

        gate_metrics = dict(gate.get("metrics", {}) or {})
        return {
            "run_id": summary.get("run_id", ""),
            "strategy": strategy_name,
            "iteration": summary.get("iteration", None),
            "gate_status": gate.get("status", ""),
            "gate_reason": gate.get("message", ""),
            "market_open": gate_metrics.get("market_open", False),
            "within_window": gate_metrics.get("within_window", True),
            "next_sleep_sec": loop_sleep_sec,
            "stage1_symbols": int((stage1.get("metrics", {}) or {}).get("stage1_universe_size", 0)),
            "stage2_input_size": int(stage2_metrics.get("stage2_input_size", 0)),
            "stage2_output_size": int(stage2_metrics.get("stage2_output_size", 0)),
            "stage2_top_filter": top_filter,
            "stage2_top_removed": int(max(0, top_removed)),
            "final_universe_size": int((stage3u.get("metrics", {}) or {}).get("final_universe_size", 0)),
            "signals_total": int((sigs.get("metrics", {}) or {}).get("signals_total", 0)),
            "orders_attempted": int((exe.get("metrics", {}) or {}).get("orders_attempted", 0)),
            "orders_submitted": int((exe.get("metrics", {}) or {}).get("orders_submitted", 0)),
            "dry_run_env": bool(ENV_DRY_RUN),
            "dry_run_effective": bool((exe.get("metrics", {}) or {}).get("dry_run", ENV_DRY_RUN)),
            "trace_file_path": str(trace_csv),
        }

    def run_once(self, strategy_name: str, ctx: StrategyContext) -> dict[str, Any]:
        if ctx.now_utc.tzinfo is None:
            ctx.now_utc = ctx.now_utc.replace(tzinfo=timezone.utc)
        data_dir = Path(ctx.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        monitor = ctx.stage_monitor if isinstance(ctx.stage_monitor, StageMonitor) else StageMonitor()
        ctx.stage_monitor = monitor
        run_id = monitor.start_run(strategy_name, ctx.iteration)
        ctx.run_id = run_id
        trace_csv = data_dir / "stage_trace.csv"
        trace_jsonl = data_dir / "stage_trace.jsonl"
        loop_sleep_sec = int(ctx.config.get("loop_sleep_sec", 60))
        closed_result: dict[str, Any] | None = None
        run_result: dict[str, Any] | None = None

        within_window = True
        try:
            cfg = ctx.config or {}
            if {"scalping_window_start_ny", "scalping_window_end_ny"}.issubset(set(cfg.keys())):
                within_window = in_ny_trading_window(
                    ctx.now_utc,
                    str(cfg.get("scalping_window_start_ny", "09:30")),
                    str(cfg.get("scalping_window_end_ny", "11:00")),
                )
        except Exception:
            within_window = True

        market_open = self._market_open_or_skip(ctx)
        if not market_open:
            self._safe_monitor_log(
                ctx,
                stage="stage0_gate",
                status="skipped",
                message="market closed / no regular session",
                metrics={
                    "market_open": False,
                    "within_window": bool(within_window),
                    "next_sleep_sec": int(loop_sleep_sec),
                },
            )
            write_run_log(
                data_dir,
                {
                    "timestamp_ny": now_ny_iso(ctx.now_utc),
                    "status": "market_closed",
                    "strategy": strategy_name,
                    "run_id": ctx.run_id,
                },
            )
            closed_result = {"status": "market_closed", "strategy": strategy_name}
        else:
            self._safe_monitor_log(
                ctx,
                stage="stage0_gate",
                status="ok",
                message="market open",
                metrics={
                    "market_open": True,
                    "within_window": bool(within_window),
                    "next_sleep_sec": int(loop_sleep_sec),
                },
            )

        if closed_result is None:
            run_result = self.dispatcher.run(strategy_name, ctx)
            now_ny = now_ny_iso(ctx.now_utc)
            append_execution_results_ledger(
                data_dir,
                strategy=strategy_name,
                execution_result=list(run_result.get("execution_result") or []),
                now_utc=ctx.now_utc,
            )

            sig_rows = []
            for s in (run_result.get("execution_result") or []):
                payload = asdict(s) if hasattr(s, "__dataclass_fields__") else {}
                sig_rows.append(
                    {
                        "timestamp_ny": now_ny,
                        "strategy": strategy_name,
                        "symbol": payload.get("symbol", ""),
                        "side": payload.get("action", ""),
                        "score": "",
                        "reasons": payload.get("error", ""),
                        "run_id": ctx.run_id,
                        "correlation_id": payload.get("correlation_id", ""),
                    }
                )
            write_signals_csv(data_dir, sig_rows)

            order_rows = []
            for r in (run_result.get("execution_result") or []):
                payload = asdict(r) if hasattr(r, "__dataclass_fields__") else {}
                order_rows.append(
                    {
                        "timestamp_ny": now_ny,
                        "strategy": strategy_name,
                        "run_id": ctx.run_id,
                        "symbol": payload.get("symbol", ""),
                        "side": payload.get("action", ""),
                        "order_type": payload.get("action", ""),
                        "qty": "",
                        "dollars": "",
                        "status": "ok" if payload.get("ok") else "error",
                        "order_id": payload.get("order_id", ""),
                        "correlation_id": payload.get("correlation_id", ""),
                    }
                )
            write_orders_csv(data_dir, order_rows)

            pos_rows = []
            for p in get_positions(ctx.trade_client):
                pos_rows.append(
                    {
                        "timestamp_ny": now_ny,
                        "strategy": strategy_name,
                        "symbol": str(getattr(p, "symbol", "")),
                        "qty": getattr(p, "qty", ""),
                        "avg_entry_price": getattr(p, "avg_entry_price", ""),
                        "market_value": getattr(p, "market_value", ""),
                        "unrealized_pl": getattr(p, "unrealized_pl", ""),
                    }
                )
            write_positions_csv(data_dir, pos_rows)

            write_run_log(
                data_dir,
                {
                    "timestamp_ny": now_ny,
                    "status": "ok",
                    "strategy": strategy_name,
                    "run_id": ctx.run_id,
                    "signals_size": run_result.get("signals_size", 0),
                    "universe_size": run_result.get("universe_size", 0),
                },
            )

        summary = monitor.finalize()
        monitor.flush_csv(trace_csv)
        monitor.flush_jsonl(trace_jsonl)
        execution_summary = self._build_execution_summary(
            summary,
            strategy_name=strategy_name,
            loop_sleep_sec=loop_sleep_sec,
            trace_csv=trace_csv,
        )

        if closed_result is not None:
            return {**closed_result, "run_id": ctx.run_id, "execution_summary": execution_summary}
        return {"status": "ok", **(run_result or {}), "run_id": ctx.run_id, "execution_summary": execution_summary}
