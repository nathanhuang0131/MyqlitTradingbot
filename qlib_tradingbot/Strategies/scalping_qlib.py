from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.config import STRAT_QLOB_SCALP, PRED_LONG_THRESHOLD, PRED_SHORT_THRESHOLD


@dataclass(frozen=True)
class ScalpSelection:
    signals: List[Signal]
    snapshot: pd.DataFrame  # rows selected with prediction + context


def signals_from_predictions(
    preds: pd.Series,
    *,
    top_n: int = 10,
    allow_shorts: bool = False,
    price_basis_by_symbol: Optional[dict] = None,
) -> ScalpSelection:
    """Create BUY/SELL signals from a prediction series.

    preds: pd.Series with MultiIndex (datetime, instrument) and numeric prediction (expected return).
    This function picks the *latest timestamp* in preds, then selects top-N long/short candidates.

    For v1:
    - Longs: pred >= PRED_LONG_THRESHOLD
    - Shorts (optional): pred <= PRED_SHORT_THRESHOLD
    """
    if preds is None or len(preds) == 0:
        return ScalpSelection(signals=[], snapshot=pd.DataFrame())

    idx = preds.index
    if not isinstance(idx, pd.MultiIndex) or idx.nlevels != 2:
        raise ValueError("preds must have MultiIndex (datetime, instrument)")

    latest_dt = idx.get_level_values(0).max()
    latest = preds.xs(latest_dt, level=0).dropna()
    if latest.empty:
        return ScalpSelection(signals=[], snapshot=pd.DataFrame())

    latest_df = latest.to_frame("pred").sort_values("pred", ascending=False)
    longs = latest_df[latest_df["pred"] >= float(PRED_LONG_THRESHOLD)].head(int(top_n))

    shorts = pd.DataFrame()
    if allow_shorts:
        shorts = latest_df[latest_df["pred"] <= float(PRED_SHORT_THRESHOLD)].tail(int(top_n))

    now_iso = datetime.now(timezone.utc).isoformat()

    signals: List[Signal] = []

    for inst, row in longs.itertuples():
        sym = str(inst).upper()
        pb = float(price_basis_by_symbol.get(sym, 0.0)) if price_basis_by_symbol else 0.0
        signals.append(
            Signal(
                symbol=sym,
                side="BUY",
                strategy_id=STRAT_QLOB_SCALP.id,
                strategy_version=STRAT_QLOB_SCALP.version,
                timeframe="5Min",
                score=float(row),
                reasons=f"QLIB pred={float(row):.6f} >= {PRED_LONG_THRESHOLD}",
                signal_ts_utc=now_iso,
                price_basis=pb,
            )
        )

    for inst, row in shorts.itertuples():
        sym = str(inst).upper()
        pb = float(price_basis_by_symbol.get(sym, 0.0)) if price_basis_by_symbol else 0.0
        signals.append(
            Signal(
                symbol=sym,
                side="SELL",
                strategy_id=STRAT_QLOB_SCALP.id,
                strategy_version=STRAT_QLOB_SCALP.version,
                timeframe="5Min",
                score=float(row),
                reasons=f"QLIB pred={float(row):.6f} <= {PRED_SHORT_THRESHOLD}",
                signal_ts_utc=now_iso,
                price_basis=pb,
                features={"intent_order_type": "BRACKET_SHORT"},
            )
        )

    snapshot = pd.concat([longs.assign(side="BUY"), shorts.assign(side="SELL")], axis=0).reset_index().rename(columns={"index": "instrument"})
    snapshot["datetime"] = latest_dt
    return ScalpSelection(signals=signals, snapshot=snapshot)
