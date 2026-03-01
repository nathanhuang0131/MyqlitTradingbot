from __future__ import annotations

from dataclasses import dataclass
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
