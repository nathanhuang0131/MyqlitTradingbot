from __future__ import annotations

import pandas as pd

from qlib_tradingbot.UI import cli


class _FakeOrchestratorOnce:
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def run_once(self, _strategy_name, _ctx):
        return {"status": "market_closed", "execution_summary": {}}


class _FakeDispatcher:
    def __init__(self, factories):
        self.factories = factories


def test_ctrl_c_returns_to_menu_no_traceback(monkeypatch, capsys):
    responses = iter(["1", "0"])

    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))
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
    monkeypatch.setattr(cli, "Orchestrator", _FakeOrchestratorOnce)
    monkeypatch.setattr(cli.time, "sleep", lambda _s: (_ for _ in ()).throw(KeyboardInterrupt()))

    cli.run_interactive()

    captured = capsys.readouterr()
    assert "Interrupted by user. Stopping current run and returning to main menu..." in captured.out
    assert captured.out.count("Select strategy:") >= 2
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


def test_analytics_no_data_returns_to_menu(monkeypatch, capsys):
    responses = iter(["5", "1", "0"])

    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))
    monkeypatch.setattr(cli, "load_trades", lambda _path: pd.DataFrame(columns=["timestamp", "realized_pnl", "fees"]))

    cli.run_interactive()

    captured = capsys.readouterr()
    assert "No data available." in captured.out
    assert "No analytics data yet - returning to main menu." in captured.out
    assert captured.out.count("Select strategy:") >= 2
