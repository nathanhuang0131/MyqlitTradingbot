from __future__ import annotations

import argparse
from pathlib import Path

from qlib_tradingbot.Analytics.performance import load_trades, daily_pnl, win_rate


def write_performance_reports(*, data_dir: str | Path = "Data", out_dir: str | Path = "Data/performance") -> tuple[Path, Path]:
    data_dir = Path(data_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ledger = data_dir / "trades_ledger.csv"
    trades = load_trades(ledger)

    pnl_df = daily_pnl(trades)
    pnl_path = out_dir / "pnl_daily.csv"
    pnl_df.to_csv(pnl_path, index=False)

    wr = win_rate(trades)
    win_path = out_dir / "win_rate.csv"
    # write as 1-row CSV for easy downstream
    import pandas as pd
    pd.DataFrame([wr]).to_csv(win_path, index=False)

    return pnl_path, win_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate PnL + win-rate CSVs from Data/trades_ledger.csv")
    ap.add_argument("--data-dir", default="Data", help="Input Data directory (expects trades_ledger.csv).")
    ap.add_argument("--out-dir", default="Data/performance", help="Output directory for reports.")
    args = ap.parse_args()

    pnl, win = write_performance_reports(data_dir=args.data_dir, out_dir=args.out_dir)
    print(f"[perf_report] wrote: {pnl}")
    print(f"[perf_report] wrote: {win}")


if __name__ == "__main__":
    main()
