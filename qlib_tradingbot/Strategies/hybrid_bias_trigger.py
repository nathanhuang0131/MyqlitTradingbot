from __future__ import annotations

"""Hybrid strategy: 5m ML bias + 1m trigger.

Idea:
  - Use the Qlib/LightGBM 5-minute prediction as a directional *bias*.
  - Only enter when 1-minute price action confirms (simple momentum trigger).

This keeps the ML model from firing purely on noise while still reacting quickly.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.config import STRAT_QLOB_SCALP, PRED_LONG_THRESHOLD, PRED_SHORT_THRESHOLD


@dataclass(frozen=True)
class HybridSelection:
    signals: List[Signal]
    snapshot: pd.DataFrame


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def signals_from_bias_and_1m_trigger(
    bias_preds: pd.Series,
    bars_1m_map: Dict[str, pd.DataFrame],
    *,
    top_n: int = 10,
    allow_shorts: bool = False,
    lookback_trigger_mins: int = 5,
    price_basis_by_symbol: Optional[dict] = None,
) -> HybridSelection:
    """Generate signals from (5m) bias + (1m) trigger.

    Long condition:
      - bias_pred >= PRED_LONG_THRESHOLD
      - 1m EMA(9) > EMA(21)
      - latest close breaks above high of previous `lookback_trigger_mins` bars

    Short condition (optional):
      - bias_pred <= PRED_SHORT_THRESHOLD
      - 1m EMA(9) < EMA(21)
      - latest close breaks below low of previous `lookback_trigger_mins` bars
    """

    if bias_preds is None or len(bias_preds) == 0:
        return HybridSelection(signals=[], snapshot=pd.DataFrame())

    idx = bias_preds.index
    if not isinstance(idx, pd.MultiIndex) or idx.nlevels != 2:
        raise ValueError("bias_preds must have MultiIndex (datetime, instrument)")

    latest_dt = idx.get_level_values(0).max()
    latest = bias_preds.xs(latest_dt, level=0).dropna()
    if latest.empty:
        return HybridSelection(signals=[], snapshot=pd.DataFrame())

    # Candidates by bias
    latest_df = latest.to_frame("pred").sort_values("pred", ascending=False)
    long_cand = latest_df[latest_df["pred"] >= float(PRED_LONG_THRESHOLD)]
    short_cand = latest_df[latest_df["pred"] <= float(PRED_SHORT_THRESHOLD)] if allow_shorts else pd.DataFrame()

    picked_rows = []
    signals: List[Signal] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    def _trigger(sym: str, side: str) -> bool:
        df = bars_1m_map.get(sym)
        if df is None or df.empty or "close" not in df.columns:
            return False
        close = pd.to_numeric(df["close"], errors="coerce").dropna()
        if len(close) < max(25, lookback_trigger_mins + 2):
            return False
        ema9 = _ema(close, 9)
        ema21 = _ema(close, 21)
        last_close = float(close.iloc[-1])

        if side == "BUY":
            prev_high = pd.to_numeric(df["high"], errors="coerce").dropna().iloc[-(lookback_trigger_mins + 1):-1].max()
            return (float(ema9.iloc[-1]) > float(ema21.iloc[-1])) and (last_close > float(prev_high))
        else:
            prev_low = pd.to_numeric(df["low"], errors="coerce").dropna().iloc[-(lookback_trigger_mins + 1):-1].min()
            return (float(ema9.iloc[-1]) < float(ema21.iloc[-1])) and (last_close < float(prev_low))

    # Evaluate triggers in bias-ranked order
    for inst, row in long_cand.itertuples():
        sym = str(inst).upper()
        if _trigger(sym, "BUY"):
            picked_rows.append({"instrument": sym, "side": "BUY", "pred": float(row), "datetime": latest_dt})
            pb = float(price_basis_by_symbol.get(sym, 0.0)) if price_basis_by_symbol else 0.0
            signals.append(
                Signal(
                    symbol=sym,
                    side="BUY",
                    strategy_id=STRAT_QLOB_SCALP.id,
                    strategy_version=f"{STRAT_QLOB_SCALP.version}+hybrid_1m",
                    timeframe="1Min",
                    score=float(row),
                    reasons=f"Bias pred={float(row):.6f} + 1m momentum trigger",
                    signal_ts_utc=now_iso,
                    price_basis=pb,
                )
            )
        if len(signals) >= int(top_n):
            break

    if allow_shorts and len(signals) < int(top_n):
        for inst, row in short_cand.sort_values("pred", ascending=True).itertuples():
            sym = str(inst).upper()
            if _trigger(sym, "SELL"):
                picked_rows.append({"instrument": sym, "side": "SELL", "pred": float(row), "datetime": latest_dt})
                pb = float(price_basis_by_symbol.get(sym, 0.0)) if price_basis_by_symbol else 0.0
                signals.append(
                    Signal(
                        symbol=sym,
                        side="SELL",
                        strategy_id=STRAT_QLOB_SCALP.id,
                        strategy_version=f"{STRAT_QLOB_SCALP.version}+hybrid_1m",
                        timeframe="1Min",
                        score=float(row),
                        reasons=f"Bias pred={float(row):.6f} + 1m momentum trigger (short)",
                        signal_ts_utc=now_iso,
                        price_basis=pb,
                        features={"intent_order_type": "BRACKET_SHORT"},
                    )
                )
            if len(signals) >= int(top_n):
                break

    snap = pd.DataFrame(picked_rows)
    return HybridSelection(signals=signals, snapshot=snap)
