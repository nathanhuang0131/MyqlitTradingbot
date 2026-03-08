from __future__ import annotations

import json
from pathlib import Path

from qlib_tradingbot.core.stage_monitor import StageMonitor


def test_stage_monitor_flush_writes_files(tmp_path: Path):
    monitor = StageMonitor()
    run_id = monitor.start_run("scalping", 1)
    monitor.log(
        stage="stage1_alpaca_fetch",
        status="ok",
        message="alpaca fetch",
        metrics={"fetch_ok": True, "symbols_returned_total": 2},
        sample_symbols=["AAPL", "MSFT"],
    )
    monitor.finalize()

    csv_path = tmp_path / "stage_trace.csv"
    jsonl_path = tmp_path / "stage_trace.jsonl"
    monitor.flush_csv(csv_path)
    monitor.flush_jsonl(jsonl_path)

    assert csv_path.exists()
    assert jsonl_path.exists()
    assert run_id in csv_path.read_text(encoding="utf-8")
    assert run_id in jsonl_path.read_text(encoding="utf-8")


def test_stage_monitor_logs_alpaca_fetch_counts():
    monitor = StageMonitor()
    monitor.start_run("scalping", 2)
    monitor.log(
        stage="stage1_alpaca_fetch",
        status="ok",
        message="alpaca fetch ok",
        metrics={"fetch_ok": True, "symbols_returned_total": 3, "duration_ms": 12},
        sample_symbols=["AAPL", "MSFT", "NVDA"],
    )
    summary = monitor.finalize()

    latest = summary["latest_by_stage"]["stage1_alpaca_fetch"]
    assert latest["metrics"]["fetch_ok"] is True
    assert latest["metrics"]["symbols_returned_total"] == 3
    assert latest["sample_symbols"] == ["AAPL", "MSFT", "NVDA"]

    # summary payload should stay JSON serializable for reporting/CLI output
    json.dumps(summary)
