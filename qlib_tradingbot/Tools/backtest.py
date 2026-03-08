from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from qlib_tradingbot.config import LABEL_HORIZON_BARS


@dataclass(frozen=True)
class BacktestResult:
    trades: pd.DataFrame
    summary: Dict[str, float]


def horizon_backtest(
    bars: pd.DataFrame,
    signals: List[dict],
    *,
    dollars_per_trade: float = 100.0,
    horizon_bars: int = LABEL_HORIZON_BARS,
) -> BacktestResult:
    """Very simple backtest:

    - Entry at the bar close at signal time.
    - Exit at close after `horizon_bars`.
    - No slippage/fees for v1.
    - Works for BUY and SELL (short) directions.
    """
    if bars is None or bars.empty or not signals:
        return BacktestResult(trades=pd.DataFrame(), summary={"trades": 0})

    df = bars.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df = df.sort_values(["symbol", "datetime"]).set_index(["symbol", "datetime"])

    rows = []
    for s in signals:
        sym = str(s.get("symbol", "")).upper()
        side = str(s.get("side", "BUY")).upper()
        ts = pd.to_datetime(s.get("datetime"), utc=True, errors="coerce")
        if not sym or ts is pd.NaT:
            continue

        try:
            entry_px = float(df.loc[(sym, ts), "close"])
        except Exception:
            # if exact ts not found, try nearest past bar
            try:
                sub = df.loc[sym]
                sub = sub[sub.index <= ts]
                if sub.empty:
                    continue
                entry_px = float(sub.iloc[-1]["close"])
                ts = sub.index[-1]
            except Exception:
                continue

        # exit
        try:
            sub = df.loc[sym]
            pos = sub.index.get_loc(ts)
            exit_pos = pos + int(horizon_bars)
            if exit_pos >= len(sub):
                continue
            exit_ts = sub.index[exit_pos]
            exit_px = float(sub.iloc[exit_pos]["close"])
        except Exception:
            continue

        qty = dollars_per_trade / entry_px if entry_px > 0 else 0.0
        if side == "SELL":
            # short: profit when price declines
            pnl = (entry_px - exit_px) * qty
            ret = (entry_px / exit_px - 1.0) if exit_px > 0 else np.nan
        else:
            pnl = (exit_px - entry_px) * qty
            ret = (exit_px / entry_px - 1.0) if entry_px > 0 else np.nan

        rows.append(
            {
                "symbol": sym,
                "side": side,
                "entry_ts": ts,
                "exit_ts": exit_ts,
                "entry_px": entry_px,
                "exit_px": exit_px,
                "dollars": dollars_per_trade,
                "qty": qty,
                "pnl": pnl,
                "ret": ret,
            }
        )

    trades = pd.DataFrame(rows)
    if trades.empty:
        return BacktestResult(trades=trades, summary={"trades": 0})

    wins = float((trades["pnl"] > 0).sum())
    total = float(len(trades))
    summary = {
        "trades": total,
        "win_rate": wins / total if total else 0.0,
        "pnl_sum": float(trades["pnl"].sum()),
        "pnl_avg": float(trades["pnl"].mean()),
    }
    return BacktestResult(trades=trades, summary=summary)


def run_backtest_from_csv(
    *,
    bars_csv: str | Path,
    signals_csv: str | Path,
    out_dir: str | Path,
    dollars_per_trade: float = 100.0,
    horizon_bars: int = LABEL_HORIZON_BARS,
) -> tuple[Path, Path]:
    bars = pd.read_csv(bars_csv)
    signals_df = pd.read_csv(signals_csv)
    if "datetime" in bars.columns:
        bars["datetime"] = pd.to_datetime(bars["datetime"], utc=True)
    signals = signals_df.to_dict(orient="records")
    result = horizon_backtest(
        bars=bars,
        signals=signals,
        dollars_per_trade=float(dollars_per_trade),
        horizon_bars=int(horizon_bars),
    )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    trades_path = out / "trades.csv"
    summary_path = out / "summary.csv"
    trades_df = result.trades.copy()
    if not trades_df.empty:
        trades_df = trades_df.sort_values(["entry_ts", "symbol"]).reset_index(drop=True)
    trades_df.to_csv(trades_path, index=False)
    pd.DataFrame([result.summary]).to_csv(summary_path, index=False)
    return trades_path, summary_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic backtest from bars/signals CSV fixtures.")
    ap.add_argument("--bars-csv", required=True)
    ap.add_argument("--signals-csv", required=True)
    ap.add_argument("--out-dir", default="Data/backtests/latest")
    ap.add_argument("--dollars-per-trade", type=float, default=100.0)
    ap.add_argument("--horizon-bars", type=int, default=LABEL_HORIZON_BARS)
    args = ap.parse_args()

    trades, summary = run_backtest_from_csv(
        bars_csv=args.bars_csv,
        signals_csv=args.signals_csv,
        out_dir=args.out_dir,
        dollars_per_trade=args.dollars_per_trade,
        horizon_bars=args.horizon_bars,
    )
    print(f"[backtest] wrote: {trades}")
    print(f"[backtest] wrote: {summary}")


if __name__ == "__main__":
    main()
