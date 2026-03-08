from __future__ import annotations

from datetime import datetime, timezone

import pytest

from qlib_tradingbot.UI import cli


class _FakeOrchestrator:
    def __init__(self, dispatcher):
        self.calls = 0

    def run_once(self, _strategy_name, _ctx):
        self.calls += 1
        if self.calls == 1:
            return {"status": "market_closed"}
        raise RuntimeError("stop_after_second_iteration")


class _FakeDispatcher:
    def __init__(self, factories):
        self.factories = factories


def test_loop_mode_market_closed_sleeps_and_rechecks(monkeypatch):
    sleeps: list[int] = []

    monkeypatch.setattr(cli, "_select_strategy", lambda: "long-term")
    monkeypatch.setattr(
        cli,
        "build_runtime_config",
        lambda _strategy: {
            "scalping_window_start_ny": "09:30",
            "scalping_window_end_ny": "11:00",
            "loop_mode": True,
            "loop_sleep_sec": 7,
            "max_symbols": 10,
            "max_positions": 5,
            "dollars_per_trade": 100.0,
            "allow_shorts": False,
        },
    )
    monkeypatch.setattr(cli, "build_clients", lambda paper: (object(), object()))
    monkeypatch.setattr(cli, "StrategyDispatcher", _FakeDispatcher)
    monkeypatch.setattr(cli, "Orchestrator", _FakeOrchestrator)
    monkeypatch.setattr(cli.time, "sleep", lambda s: sleeps.append(int(s)))

    with pytest.raises(RuntimeError, match="stop_after_second_iteration"):
        cli.run_once_interactive()

    assert sleeps
    assert sleeps[0] == 7
