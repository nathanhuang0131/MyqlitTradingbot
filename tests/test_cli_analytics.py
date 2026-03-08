from __future__ import annotations

import pandas as pd

from qlib_tradingbot.UI.cli import build_analytics_view


def _trades_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-03-01T20:00:00Z",
                "strategy": "scalping",
                "symbol": "AAPL",
                "side": "SELL",
                "qty": 1,
                "fill_price": 100,
                "order_id": "1",
                "event": "CLOSE",
                "realized_pnl": 20,
                "fees": 1,
                "tags": "",
            }
        ]
    )


def test_analytics_cli_views_have_expected_headers():
    trades = _trades_df()

    title_day, day = build_analytics_view("1", trades)
    title_wr, wr = build_analytics_view("2", trades)
    title_sym, sym = build_analytics_view("3", trades)
    title_strat, strat = build_analytics_view("4", trades)

    assert title_day == "Daily P&L"
    assert "day" in day.columns
    assert title_wr == "Win Rate"
    assert "win_rate" in wr.columns
    assert title_sym == "By Symbol"
    assert "symbol" in sym.columns
    assert title_strat == "By Strategy"
    assert "strategy" in strat.columns
