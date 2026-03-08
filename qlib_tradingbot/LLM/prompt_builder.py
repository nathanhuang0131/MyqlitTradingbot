from __future__ import annotations

from datetime import datetime
from typing import Iterable


def build_post_market_prompt(
    *,
    as_of_date: str,
    strategy_type: str,
    csv_filename: str,
    symbols: Iterable[str],
) -> str:
    symbol_list = ", ".join(sorted({str(s).upper() for s in symbols if str(s).strip()})) or "(none)"
    return (
        f"Post-Market Review Request ({as_of_date})\n"
        f"Strategy profile: {strategy_type}\n"
        f"Input data file: {csv_filename}\n"
        f"Symbols: {symbol_list}\n\n"
        "Please analyze this portfolio and provide:\n"
        "1) Portfolio risk summary\n"
        "2) Symbol-by-symbol bias (bullish/bearish/neutral)\n"
        "3) Probability % for each symbol view\n"
        "4) Key signals to watch next session\n"
        "5) Suggested action per symbol (hold/trim/exit/add)\n"
        "6) Incorporate relevant news + market trend context\n\n"
        "Output format (strict):\n"
        "SYMBOL: <ticker>\n"
        "BIAS: Bullish|Bearish|Neutral\n"
        "PROB: <0-100>\n"
        "ACTION: Hold|Trim|Exit|Add\n"
    )


def dated_filename(prefix: str, when_utc: datetime, ext: str) -> str:
    return f"{prefix}_{when_utc.strftime('%Y%m%d')}.{ext}"
