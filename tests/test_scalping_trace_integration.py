from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.UI import cli


class _FakeAsset:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.asset_class = "us_equity"
        self.tradable = True
        self.exchange = "NYSE"


class _FakeTradeClient:
    def get_clock(self):
        return type(
            "Clock",
            (),
            {
                "is_open": True,
                "next_open": datetime(2026, 3, 2, 14, 30, tzinfo=timezone.utc),
                "next_close": datetime(2026, 3, 2, 21, 0, tzinfo=timezone.utc),
            },
        )()

    def get_all_positions(self):
        return []


def test_scalping_trace_shows_top_filter_and_single_summary(monkeypatch, tmp_path: Path, capsys):
    data_dir = tmp_path / "Data"
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(cli, "_select_strategy", lambda: "scalping")
    monkeypatch.setattr(
        cli,
        "build_runtime_config",
        lambda _strategy: {
            "scalping_window_start_ny": "09:30",
            "scalping_window_end_ny": "11:00",
            "loop_mode": False,
            "loop_sleep_sec": 1,
            "max_symbols": 10,
            "max_positions": 5,
            "dollars_per_trade": 100.0,
            "allow_shorts": False,
        },
    )
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "build_clients", lambda paper: (object(), _FakeTradeClient()))

    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.scalp_pipeline_qlib.fetch_alpaca_active_assets",
        lambda _tc: [_FakeAsset("AAPL"), _FakeAsset("MSFT"), _FakeAsset("NVDA")],
    )

    def _daily_bars_all_fail(_dc, *, symbols, lookback_days, cfg):  # noqa: ARG001
        out = {}
        for s in symbols:
            out[s] = pd.DataFrame(
                {
                    "timestamp": pd.date_range("2026-02-01", periods=25, freq="D", tz="UTC"),
                    "open": [5.0] * 25,
                    "high": [5.1] * 25,
                    "low": [4.9] * 25,
                    "close": [5.0] * 25,
                    "volume": [3_000_000.0] * 25,
                }
            )
        return out

    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.scalp_pipeline_qlib.get_daily_bars_batched",
        _daily_bars_all_fail,
    )
    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.scalping_strategy.fetch_1m_bars_batch",
        lambda *_a, **_k: {},
    )

    cli.run_once_interactive()
    out = capsys.readouterr().out

    assert out.count("EXECUTION_SUMMARY") == 1
    assert "Cycle " in out
    assert "dry_run_effective=" in out
    assert "Top suppressors:" in out

    trace_path = data_dir / "stage_trace.jsonl"
    assert trace_path.exists()
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    stage2 = [e for e in events if e.get("stage") == "stage2_filters"]
    assert stage2
    breakdown = stage2[-1]["metrics"]["filters_breakdown"]
    assert breakdown["min_price"]["removed"] == 3
