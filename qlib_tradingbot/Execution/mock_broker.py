from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from qlib_tradingbot.core.models import OrderIntent
from qlib_tradingbot.Execution.orders import OrderResult


class MockExecutionEngine:
    """No-op execution path used for dry runs.

    Writes intended orders to CSV + JSONL under Data/trade_history by default.
    """

    def __init__(self, output_dir: Optional[Path | str] = None) -> None:
        self.output_dir = Path(output_dir) if output_dir is not None else Path("Data") / "trade_history"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.output_dir / "mock_orders.csv"
        self.jsonl_path = self.output_dir / "mock_orders.jsonl"

    def record(self, intent: OrderIntent, *, correlation_id: Optional[str] = None) -> OrderResult:
        now = datetime.now(timezone.utc).isoformat()
        order_id = f"MOCK-{uuid4()}"
        payload = {
            "timestamp_utc": now,
            "symbol": intent.symbol,
            "side": intent.side,
            "order_type": intent.order_type,
            "dollars": intent.dollars,
            "qty": intent.qty,
            "stop_price": intent.stop_price,
            "take_profit_price": intent.take_profit_price,
            "run_id": intent.run_id,
            "correlation_id": correlation_id or intent.correlation_id,
            "strategy_id": intent.strategy_id,
            "strategy_version": intent.strategy_version,
            "order_id": order_id,
            "intent": asdict(intent),
        }

        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True, default=str) + "\n")

        header = [
            "timestamp_utc",
            "symbol",
            "side",
            "order_type",
            "dollars",
            "qty",
            "stop_price",
            "take_profit_price",
            "run_id",
            "correlation_id",
            "strategy_id",
            "strategy_version",
            "order_id",
        ]
        row = ",".join(
            [
                str(payload.get("timestamp_utc", "")),
                str(payload.get("symbol", "")),
                str(payload.get("side", "")),
                str(payload.get("order_type", "")),
                str(payload.get("dollars", "")),
                str(payload.get("qty", "")),
                str(payload.get("stop_price", "")),
                str(payload.get("take_profit_price", "")),
                str(payload.get("run_id", "")),
                str(payload.get("correlation_id", "")),
                str(payload.get("strategy_id", "")),
                str(payload.get("strategy_version", "")),
                str(payload.get("order_id", "")),
            ]
        )
        if not self.csv_path.exists():
            self.csv_path.write_text(",".join(header) + "\n", encoding="utf-8")
        with self.csv_path.open("a", encoding="utf-8") as f:
            f.write(row + "\n")

        return OrderResult(
            ok=True,
            symbol=intent.symbol,
            action=intent.order_type.upper(),
            submitted=False,
            order_id=order_id,
            correlation_id=correlation_id or intent.correlation_id,
        )
