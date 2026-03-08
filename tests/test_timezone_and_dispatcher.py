from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher
from qlib_tradingbot.Utils.timezone_utils import (
    NY_TZ,
    SYDNEY_TZ,
    format_session_window,
    in_ny_trading_window,
    to_new_york,
)


def test_to_new_york_converts_from_sydney_correctly_with_dst():
    # Sydney summer (AEDT), US winter (EST)
    sydney_local = datetime(2026, 1, 15, 10, 0, tzinfo=SYDNEY_TZ)
    ny = to_new_york(sydney_local)
    assert ny.tzinfo == NY_TZ
    assert ny.hour == 18
    assert ny.day == 14


def test_in_ny_trading_window_for_default_scalping_hours():
    ny_inside = datetime(2026, 3, 2, 10, 15, tzinfo=NY_TZ)
    ny_before = datetime(2026, 3, 2, 9, 29, tzinfo=NY_TZ)
    ny_after = datetime(2026, 3, 2, 11, 1, tzinfo=NY_TZ)

    assert in_ny_trading_window(ny_inside, "09:30", "11:00")
    assert not in_ny_trading_window(ny_before, "09:30", "11:00")
    assert not in_ny_trading_window(ny_after, "09:30", "11:00")


def test_format_session_window_shows_ny_and_sydney():
    now_utc = datetime(2026, 3, 2, 14, 35, tzinfo=timezone.utc)
    output = format_session_window(now_utc, "09:30", "11:00")
    assert "New York" in output
    assert "Sydney" in output
    assert "09:30" in output
    assert "11:00" in output


@dataclass
class _Recorder:
    calls: list[str]


class _FakeStrategy(StrategyBase):
    strategy_id = "fake"

    def __init__(self, rec: _Recorder):
        self._rec = rec

    def build_universe(self):
        self._rec.calls.append("build_universe")
        return ["AAPL"]

    def prepare_features(self, universe):
        self._rec.calls.append("prepare_features")
        return {"universe": universe}

    def generate_signals(self, features):
        self._rec.calls.append("generate_signals")
        return []

    def execute(self, signals):
        self._rec.calls.append("execute")
        return []

    def post_trade_reporting(self):
        self._rec.calls.append("post_trade_reporting")
        return {}


def test_dispatcher_runs_strategy_pipeline_in_order():
    rec = _Recorder(calls=[])
    dispatcher = StrategyDispatcher(
        {
            "fake": lambda _ctx: _FakeStrategy(rec),
        }
    )
    ctx = StrategyContext(run_id="r1", now_utc=datetime(2026, 3, 2, 14, 35, tzinfo=timezone.utc))
    dispatcher.run("fake", ctx)
    assert rec.calls == [
        "build_universe",
        "prepare_features",
        "generate_signals",
        "execute",
        "post_trade_reporting",
    ]
