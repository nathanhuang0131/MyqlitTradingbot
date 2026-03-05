from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.dispatcher import StrategyDispatcher
from qlib_tradingbot.Strategies.intraday_strategy import IntradayStrategy
from qlib_tradingbot.Strategies.llm_planner_strategy import LLMPlannerStrategy
from qlib_tradingbot.Strategies.position_model_strategies import LongTermStrategy, ShortTermStrategy
from qlib_tradingbot.Strategies.scalping_strategy import ScalpingStrategy


@dataclass
class _Pos:
    symbol: str
    qty: str = "1"


class _FakeTradeClient:
    def __init__(self, positions=None):
        self._positions = positions or []

    def get_all_positions(self):
        return self._positions


def _ctx(trade_client=None):
    return StrategyContext(
        run_id="r1",
        correlation_id="c1",
        now_utc=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
        config={"universe_symbols": ["AAPL", "MSFT", "NVDA"], "force_eod_flat": True},
        data_client=object(),
        trade_client=trade_client or _FakeTradeClient(),
    )


def test_dispatcher_selects_each_strategy():
    dispatcher = StrategyDispatcher(
        {
            "intraday": lambda ctx: IntradayStrategy(ctx),
            "short-term": lambda ctx: ShortTermStrategy(ctx),
            "long-term": lambda ctx: LongTermStrategy(ctx),
            "llm-planner": lambda ctx: LLMPlannerStrategy(ctx),
        }
    )
    for name in ["intraday", "short-term", "long-term", "llm-planner"]:
        s = dispatcher.build(name, _ctx())
        assert s.strategy_id


def test_short_term_strategy_position_aware_decisions(monkeypatch):
    strategy = ShortTermStrategy(_ctx(_FakeTradeClient(positions=[_Pos("AAPL")])))
    idx = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2026-03-02T14:55:00Z"), "AAPL"),
            (pd.Timestamp("2026-03-02T14:55:00Z"), "MSFT"),
            (pd.Timestamp("2026-03-02T14:55:00Z"), "NVDA"),
        ],
        names=["datetime", "symbol"],
    )
    preds = pd.Series([-0.02, 0.03, 0.01], index=idx)
    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.position_model_strategies.stage3_qlib_score",
        lambda *a, **k: (preds, pd.DataFrame()),
    )

    features = strategy.prepare_features(["AAPL", "MSFT", "NVDA"])
    signals = strategy.generate_signals(features)
    sides = {(s.symbol, s.side) for s in signals}
    assert ("AAPL", "SELL") in sides
    assert ("MSFT", "BUY") in sides


def test_llm_planner_strategy_is_deterministic_stub():
    prompt_path = Path("Data/llm_prompt_test.txt")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Template with BUY and HOLD", encoding="utf-8")
    ctx = _ctx()
    ctx.config["llm_prompt_path"] = str(prompt_path)
    strategy = LLMPlannerStrategy(ctx)
    signals = strategy.generate_signals({"universe": ["AAPL", "MSFT"]})
    assert len(signals) == 2
    assert signals[0].symbol == "AAPL"


def test_scalping_dispatch_calls_stage_pipeline(monkeypatch):
    called = {"pipeline": 0}
    out_dir = Path("Data/test_dispatch_scalping")
    out_dir.mkdir(parents=True, exist_ok=True)

    def _fake_pipeline(*args, **kwargs):
        called["pipeline"] += 1
        out = Path(kwargs["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"Symbol": ["AAPL"]}).to_csv(out / "universe_trade_today.csv", index=False)
        return {"ok": True}

    monkeypatch.setattr("qlib_tradingbot.Strategies.scalping_strategy.run_3stage_qlib_scalp_pipeline", _fake_pipeline)
    monkeypatch.setattr(
        "qlib_tradingbot.Strategies.scalping_strategy.QlibSignalEngine.run",
        lambda *a, **k: pd.DataFrame(columns=["symbol", "timestamp", "alpha", "direction", "confidence", "horizon", "model_id"]),
    )
    monkeypatch.setattr("qlib_tradingbot.Strategies.scalping_strategy.fetch_1m_bars_batch", lambda *a, **k: {})

    dispatcher = StrategyDispatcher({"scalping": lambda ctx: ScalpingStrategy(ctx)})
    dispatcher.run(
        "scalping",
        StrategyContext(
            run_id="r2",
            correlation_id="c2",
            now_utc=datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
            data_dir=str(out_dir),
            data_client=object(),
            trade_client=_FakeTradeClient(),
            config={"scalping_window_start_ny": "09:30", "scalping_window_end_ny": "11:00"},
        ),
    )
    assert called["pipeline"] == 1
