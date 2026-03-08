
import pandas as pd

from qlib_tradingbot.Strategies.scalp_pipeline_qlib import (
    Stage1Config,
    Stage2Config,
    stage1_reduce_universe,
    stage2_liquidity_filter,
)
from qlib_tradingbot.Data.batch_bars import BatchFetchConfig


class A:
    def __init__(self, symbol, tradable=True, asset_class="us_equity", exchange="NASDAQ"):
        self.symbol = symbol
        self.tradable = tradable
        self.asset_class = asset_class
        self.exchange = exchange


class FakeDataClient:
    pass


def test_stage1_reduce_universe_basic():
    assets = [
        A("AAPL", True, "us_equity", "NASDAQ"),
        A("MSFT", True, "us_equity", "NASDAQ"),
        A("ZZZZ", False, "us_equity", "NASDAQ"),
        A("OTC1", True, "us_equity", "OTC"),
    ]
    syms = stage1_reduce_universe(assets, Stage1Config(tradable_only=True, allow_otc=False))
    assert "AAPL" in syms and "MSFT" in syms
    assert "ZZZZ" not in syms
    assert "OTC1" not in syms


def test_stage2_liquidity_filter_uses_bars_map(monkeypatch, tmp_path):
    # monkeypatch fetch_daily_bars_batch to return synthetic bars
    from qlib_tradingbot import Data
    import qlib_tradingbot.Data.batch_bars as bb

    def fake_fetch_daily_bars_batch(data_client, *, symbols, lookback_days=60, feed=None, regular_session_only=True, cfg=BatchFetchConfig(), test_mode=False):
        out = {}
        for s in symbols:
            # 30 days of bars
            dt = pd.date_range("2025-01-01", periods=30, freq="D", tz="UTC")
            close = pd.Series([100.0] * 30)
            df = pd.DataFrame({
                "datetime": dt,
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": [3_000_000] * 30
            })
            out[str(s).upper()] = df
        return out

    import qlib_tradingbot.Strategies.scalp_pipeline_qlib as pipe
    monkeypatch.setattr(pipe, "get_daily_bars_batched", fake_fetch_daily_bars_batch)

    passed, funnel, bars_map = stage2_liquidity_filter(
        FakeDataClient(),
        symbols=["AAPL", "MSFT"],
        cfg=Stage2Config(min_price=15, min_avg_volume_20d=2_000_000, min_atr_pct_14d=0.005, max_spread_proxy_20d=0.05, keep_top_n=10),
        batch_cfg=BatchFetchConfig(),
        lookback_days=60,
    )
    assert not passed.empty
    assert set(passed["Symbol"]) == {"AAPL", "MSFT"}
    assert funnel["Pass"].all()
    assert set(bars_map.keys()) == {"AAPL", "MSFT"}
