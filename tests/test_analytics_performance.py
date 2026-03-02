from __future__ import annotations

from pathlib import Path

from qlib_tradingbot.Analytics.performance import (
    breakdown_by_strategy,
    breakdown_by_symbol,
    daily_pnl,
    load_trades,
    win_rate,
)


def test_daily_pnl_and_win_rate_from_fixture_ledger(tmp_path: Path):
    ledger = tmp_path / "trades_ledger.csv"
    ledger.write_text(
        "timestamp,strategy,symbol,side,qty,fill_price,order_id,event,realized_pnl,fees,tags\n"
        "2026-03-01T20:00:00Z,scalping,AAPL,SELL,1,101,OID1,CLOSE,50,2,\n"
        "2026-03-01T20:30:00Z,scalping,MSFT,SELL,1,201,OID2,CLOSE,-20,1,\n"
        "2026-03-02T15:00:00Z,intraday,NVDA,SELL,1,301,OID3,CLOSE,30,3,\n",
        encoding="utf-8",
    )

    trades = load_trades(ledger)
    by_day = daily_pnl(trades)
    wr = win_rate(trades)

    assert len(by_day) == 2
    assert by_day.iloc[0]["day"] == "2026-03-01"
    assert float(by_day.iloc[0]["net_pnl"]) == 27.0
    assert by_day.iloc[1]["day"] == "2026-03-02"
    assert float(by_day.iloc[1]["net_pnl"]) == 27.0

    assert wr["wins"] == 2
    assert wr["losses"] == 1
    assert round(float(wr["win_rate"]), 4) == 0.6667
    assert round(float(wr["profit_factor"]), 2) == 3.57


def test_breakdowns_have_expected_groups(tmp_path: Path):
    ledger = tmp_path / "trades_ledger.csv"
    ledger.write_text(
        "timestamp,strategy,symbol,side,qty,fill_price,order_id,event,realized_pnl,fees,tags\n"
        "2026-03-01T20:00:00Z,scalping,AAPL,SELL,1,101,OID1,CLOSE,10,1,\n"
        "2026-03-01T21:00:00Z,scalping,AAPL,SELL,1,102,OID2,CLOSE,5,1,\n"
        "2026-03-01T22:00:00Z,intraday,MSFT,SELL,1,200,OID3,CLOSE,-7,1,\n",
        encoding="utf-8",
    )
    trades = load_trades(ledger)

    sym = breakdown_by_symbol(trades)
    strat = breakdown_by_strategy(trades)

    assert set(sym["symbol"].tolist()) == {"AAPL", "MSFT"}
    assert set(strat["strategy"].tolist()) == {"scalping", "intraday"}
