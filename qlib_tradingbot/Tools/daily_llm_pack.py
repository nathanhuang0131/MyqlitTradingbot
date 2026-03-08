from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from qlib_tradingbot.LLM.prompt_builder import build_post_market_prompt, dated_filename
from qlib_tradingbot.LLM.post_market_review import CSV_COLUMNS, _compute_indicators


def _table_markdown(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except ImportError:
        cols = [str(c) for c in df.columns]
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        rows = []
        for _, row in df.iterrows():
            rows.append("| " + " | ".join([str(row.get(c, "")) for c in df.columns]) + " |")
        return "\n".join([header, sep] + rows)


def _make_feedback_template(path: Path, symbols: list[str]) -> Path:
    """
    CSV template the user can paste LLM outputs into (or fill manually).
    The ingest tool will convert this CSV into the strict text format required
    by qlib_tradingbot.LLM.feedback_handler.parse_feedback_text().
    """
    rows = []
    for sym in sorted({s.upper() for s in symbols if str(s).strip()}):
        rows.append(
            {
                "symbol": sym,
                "bias": "Neutral",   # Bullish|Bearish|Neutral
                "prob": 50,          # 0-100
                "action": "Hold",    # Hold|Trim|Exit|Add
                "notes": "",
            }
        )
    df = pd.DataFrame(rows, columns=["symbol", "bias", "prob", "action", "notes"])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def _write_summary_md(path: Path, upload_df: pd.DataFrame, strategy_type: str, as_of: str) -> Path:
    # Keep it deterministic: summary is a simple structured recap.
    pos = upload_df[upload_df["row_type"] == "position"].copy()
    mkt = upload_df[upload_df["row_type"] == "market_context"].copy()

    lines: list[str] = []
    lines.append(f"# Post-market summary ({as_of})")
    lines.append("")
    lines.append(f"- Strategy profile: **{strategy_type}**")
    lines.append(f"- Positions: **{len(pos)}**")
    lines.append("")

    if not pos.empty:
        cols = ["symbol", "qty", "avg_entry", "current_price", "unrealized_pnl", "rsi14", "macd", "vwap"]
        cols = [c for c in cols if c in pos.columns]
        lines.append("## Open positions snapshot")
        lines.append("")
        lines.append(_table_markdown(pos[cols]))
        lines.append("")

    if not mkt.empty:
        lines.append("## Market context (SPY)")
        lines.append("")
        cols = ["symbol", "rsi14", "macd", "vwap", "volume_vs_avg"]
        cols = [c for c in cols if c in mkt.columns]
        lines.append(_table_markdown(mkt[cols]))
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _dry_run_rows(now: datetime, strategy_type: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Deterministic, offline-friendly example data.
    """
    symbols = ["AAPL", "MSFT", "NVDA"]
    rows: list[dict[str, Any]] = []
    for sym in symbols:
        rows.append(
            {
                "timestamp": now.isoformat(),
                "row_type": "position",
                "strategy_type": strategy_type,
                "symbol": sym,
                "qty": 1,
                "avg_entry": 100.0,
                "current_price": 101.0,
                "unrealized_pnl": 1.0,
                "timeframe": "1h",
                "rsi14": 55.0,
                "macd": 0.2,
                "macd_signal": 0.1,
                "ema9": 100.5,
                "ema21": 99.8,
                "atr14": 2.0,
                "vwap": 100.2,
                "volume_vs_avg": 1.1,
                "notes": "dry-run sample",
            }
        )

    # SPY context row
    rows.append(
        {
            "timestamp": now.isoformat(),
            "row_type": "market_context",
            "strategy_type": strategy_type,
            "symbol": "SPY",
            "qty": "",
            "avg_entry": "",
            "current_price": "",
            "unrealized_pnl": "",
            "timeframe": "1h",
            "rsi14": 52.0,
            "macd": 0.1,
            "macd_signal": 0.08,
            "ema9": 0.0,
            "ema21": 0.0,
            "atr14": 0.0,
            "vwap": 0.0,
            "volume_vs_avg": 1.0,
            "notes": "SPY trend snapshot (dry-run)",
        }
    )

    df = pd.DataFrame(rows)
    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[CSV_COLUMNS]
    return df, symbols


def generate_daily_llm_pack(
    *,
    out_root: str | Path,
    strategy_type: str,
    dry_run: bool,
    now_utc: datetime | None = None,
) -> Path:
    now = now_utc or datetime.now(timezone.utc)
    as_of = now.strftime("%Y-%m-%d")
    out_root = Path(out_root)
    out_dir = out_root / as_of
    out_dir.mkdir(parents=True, exist_ok=True)

    upload_name = dated_filename("llm_upload", now, "csv")
    prompt_name = dated_filename("llm_prompt", now, "txt")
    upload_path = out_dir / upload_name
    prompt_path = out_dir / prompt_name
    summary_path = out_dir / "summary.md"
    template_path = out_dir / "feedback_template.csv"

    if dry_run:
        upload_df, symbols = _dry_run_rows(now, strategy_type)
    else:
        # Online mode is intentionally not implemented here. The repo already has a
        # live pack generator in qlib_tradingbot.LLM.post_market_review.generate_post_market_package().
        raise SystemExit("Non-dry-run mode not supported by this tool yet. Use LLM/post_market_review.py instead.")

    upload_df.to_csv(upload_path, index=False)

    prompt = build_post_market_prompt(
        as_of_date=as_of,
        strategy_type=strategy_type,
        csv_filename=upload_name,
        symbols=symbols,
    )
    prompt_path.write_text(prompt, encoding="utf-8")

    _write_summary_md(summary_path, upload_df, strategy_type, as_of)
    _make_feedback_template(template_path, symbols)

    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a daily LLM upload + prompt + feedback template (offline-friendly).")
    ap.add_argument("--out", default="Data/llm_daily_pack", help="Output root directory.")
    ap.add_argument("--strategy-type", default="short-term", help="Strategy profile label (short-term|intraday|scalping|long-term).")
    ap.add_argument("--dry-run", action="store_true", help="Generate deterministic sample artifacts (no broker/data calls).")
    args = ap.parse_args()

    out_dir = generate_daily_llm_pack(out_root=args.out, strategy_type=args.strategy_type, dry_run=args.dry_run)
    print(f"[daily_llm_pack] wrote: {out_dir}")


if __name__ == "__main__":
    main()
