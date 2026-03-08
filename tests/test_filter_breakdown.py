from __future__ import annotations

from qlib_tradingbot.Strategies.scalp_pipeline_qlib import apply_filters_with_breakdown


def test_stage2_filter_breakdown_counts_removed():
    symbols = ["AAPL", "MSFT", "TSLA", "PENNY"]
    filters = [
        ("drop_penny", lambda s: s != "PENNY"),
        ("drop_ticker_t", lambda s: not s.startswith("T")),
    ]

    symbols_out, breakdown = apply_filters_with_breakdown(symbols, filters)

    assert symbols_out == ["AAPL", "MSFT"]
    assert breakdown["drop_penny"]["in_count"] == 4
    assert breakdown["drop_penny"]["out_count"] == 3
    assert breakdown["drop_penny"]["removed"] == 1
    assert breakdown["drop_ticker_t"]["in_count"] == 3
    assert breakdown["drop_ticker_t"]["out_count"] == 2
    assert breakdown["drop_ticker_t"]["removed"] == 1
