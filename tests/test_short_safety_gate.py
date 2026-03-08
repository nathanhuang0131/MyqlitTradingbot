from __future__ import annotations

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Execution import orders
from qlib_tradingbot.Execution.engine import execute_signals
from qlib_tradingbot.Execution.shorting import preflight_allow_shorts


class _Account:
    shorting_enabled = False
    multiplier = "1"
    account_type = "cash"


class _TradeClientNoShort:
    def get_account(self):
        return _Account()

    def get_all_positions(self):
        return []


class _SubmitSpy:
    def __init__(self):
        self.calls = 0

    def submit_order(self, _req):
        self.calls += 1
        return {"id": "OID"}


def test_preflight_disables_shorting_without_margin_support():
    logs: list[str] = []
    allowed = preflight_allow_shorts(_TradeClientNoShort(), True, logger=logs.append)
    assert allowed is False
    assert logs
    assert "disabling allow_shorts" in logs[0]


def test_engine_skips_short_intent_when_allow_shorts_false(monkeypatch):
    monkeypatch.setattr("qlib_tradingbot.Execution.engine.execute_intent", lambda *a, **k: None)
    tc = _TradeClientNoShort()
    sig = Signal(
        symbol="AAPL",
        side="SELL",
        strategy_id="S",
        strategy_version="1",
        timeframe="1Min",
        features={"intent_order_type": "BRACKET_SHORT"},
    )

    out = execute_signals(tc, [sig], allow_shorts=False)

    assert out[0].action == "SKIP"
    assert "short selling disabled" in (out[0].error or "")


def test_dry_run_submit_does_not_call_broker(monkeypatch):
    spy = _SubmitSpy()
    monkeypatch.setattr(orders, "DRY_RUN", True)

    result = orders._submit(spy, {"kind": "test"})

    assert spy.calls == 0
    assert result.get("dry_run") is True
