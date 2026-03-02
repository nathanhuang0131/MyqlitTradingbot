from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qlib_tradingbot.Brokers.alpaca_gateway import get_market_clock, get_positions
from qlib_tradingbot.Analytics.ledger import append_execution_results_ledger
from qlib_tradingbot.Reporting.reporting import (
    now_ny_iso,
    write_orders_csv,
    write_positions_csv,
    write_run_log,
    write_signals_csv,
)
from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher


class Orchestrator:
    def __init__(self, dispatcher: StrategyDispatcher):
        self.dispatcher = dispatcher

    def _market_open_or_skip(self, ctx: StrategyContext) -> bool:
        clk = get_market_clock(ctx.trade_client)
        if clk.is_open:
            return True
        print("market closed / no regular session")
        if ctx.config.get("loop_mode", False):
            print("loop mode enabled: sleep/retry on next cycle")
        return False

    def run_once(self, strategy_name: str, ctx: StrategyContext) -> dict[str, Any]:
        if ctx.now_utc.tzinfo is None:
            ctx.now_utc = ctx.now_utc.replace(tzinfo=timezone.utc)
        data_dir = Path(ctx.data_dir)
        if not self._market_open_or_skip(ctx):
            write_run_log(
                data_dir,
                {
                    "timestamp_ny": now_ny_iso(ctx.now_utc),
                    "status": "market_closed",
                    "strategy": strategy_name,
                    "run_id": ctx.run_id,
                },
            )
            return {"status": "market_closed", "strategy": strategy_name}

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
        return {"status": "ok", **run_result}
