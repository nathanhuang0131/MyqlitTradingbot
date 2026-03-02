from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.LLM.post_market_review import CSV_COLUMNS, generate_post_market_package


class _Pos:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.qty = "2"
        self.avg_entry_price = "100"
        self.current_price = "101"
        self.unrealized_pl = "2"


class _TradeClient:
    def get_all_positions(self):
        return [_Pos("AAPL")]


class _EmptyTradeClient:
    def get_all_positions(self):
        return []


def test_post_market_package_creates_csv_and_prompt(tmp_path: Path):
    csv_path, prompt_path = generate_post_market_package(
        data_dir=tmp_path,
        trade_client=_TradeClient(),
        data_client=None,
        strategy_type="intraday",
        now_utc=datetime(2026, 3, 2, 22, 0, tzinfo=timezone.utc),
    )

    assert csv_path.exists()
    assert prompt_path.exists()

    df = pd.read_csv(csv_path)
    assert all(c in df.columns for c in CSV_COLUMNS)
    text = prompt_path.read_text(encoding="utf-8")
    assert "Portfolio risk summary" in text
    assert "bias" in text.lower()
    assert "Probability %" in text
    assert "hold/trim/exit/add" in text.lower()


def test_post_market_package_handles_missing_data_gracefully(tmp_path: Path):
    csv_path, prompt_path = generate_post_market_package(
        data_dir=tmp_path,
        trade_client=_EmptyTradeClient(),
        data_client=None,
        strategy_type="long-term",
        now_utc=datetime(2026, 3, 2, 22, 0, tzinfo=timezone.utc),
    )

    assert csv_path.exists()
    assert prompt_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) >= 1
    assert "SPY" in set(df["symbol"].astype(str).tolist())
