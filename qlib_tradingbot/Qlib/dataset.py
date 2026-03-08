from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from qlib_tradingbot.config import LABEL_HORIZON_BARS

# Qlib data objects are optional at import-time for unit tests
try:  # pragma: no cover
    from qlib.data.dataset.loader import StaticDataLoader
    from qlib.data.dataset.handler import DataHandlerLP
    from qlib.data.dataset import DatasetH
    from qlib.data.dataset.processor import (
        DropnaLabel,
        Fillna,
        ZScoreNorm,
    )
    QLIB_DATA_AVAILABLE = True
except Exception:  # pragma: no cover
    StaticDataLoader = DataHandlerLP = DatasetH = object  # type: ignore
    DropnaLabel = Fillna = ZScoreNorm = object  # type: ignore
    QLIB_DATA_AVAILABLE = False


@dataclass(frozen=True)
class QlibDatasetBundle:
    raw: pd.DataFrame
    dataset: object
    handler: object
    features: List[str]


def _compute_features(bars: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Compute a small, scalping-friendly feature set from OHLCV bars.

    Input bars columns expected: symbol, datetime, open, high, low, close, volume
    Output: multi-index (datetime, instrument) + feature columns + label column.
    """
    df = bars.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df["instrument"] = df["symbol"].astype(str).str.upper()
    df = df.sort_values(["instrument", "datetime"]).set_index(["datetime", "instrument"])

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["volume"].astype(float)

    # basic bar stats
    ret1 = close.groupby(level=1).pct_change().fillna(0.0)
    hl_range = (high - low) / close.replace(0, np.nan)
    vwap_proxy = (df["open"].astype(float) + high + low + close) / 4.0
    vwap_dist = (close - vwap_proxy) / close.replace(0, np.nan)

    # simple rolling features (per-instrument)
    def groll(s, w, fn):
        return s.groupby(level=1).rolling(w).apply(fn, raw=True).reset_index(level=0, drop=True)

    # rolling mean volume and rvol proxy
    vol_ma20 = vol.groupby(level=1).rolling(20).mean().reset_index(level=0, drop=True)
    rvol = (vol / vol_ma20.replace(0, np.nan)).clip(0, 10)

    # momentum windows
    mom3 = close.groupby(level=1).pct_change(3)
    mom6 = close.groupby(level=1).pct_change(6)

    # volatility proxy
    volat20 = ret1.groupby(level=1).rolling(20).std().reset_index(level=0, drop=True)

    feat = pd.DataFrame(
        {
            "RET1": ret1,
            "RANGE": hl_range.replace([np.inf, -np.inf], np.nan),
            "VWAP_DIST": vwap_dist.replace([np.inf, -np.inf], np.nan),
            "RVOL": rvol.replace([np.inf, -np.inf], np.nan),
            "MOM3": mom3.replace([np.inf, -np.inf], np.nan),
            "MOM6": mom6.replace([np.inf, -np.inf], np.nan),
            "VOLAT20": volat20.replace([np.inf, -np.inf], np.nan),
        }
    )

    # Label: forward return over next N bars (per instrument)
    horizon = int(LABEL_HORIZON_BARS)
    fwd = close.groupby(level=1).shift(-horizon)
    label = (fwd / close) - 1.0
    feat["LABEL0"] = label

    features = ["RET1", "RANGE", "VWAP_DIST", "RVOL", "MOM3", "MOM6", "VOLAT20"]
    return feat, features


def build_qlib_dataset_from_bars(
    bars: pd.DataFrame,
    *,
    train_start: str,
    train_end: str,
    valid_end: str,
    test_end: str,
) -> QlibDatasetBundle:
    """Build a Qlib DatasetH from Alpaca bars (no Qlib provider needed).

    This uses `StaticDataLoader` (in-memory/file-based loading) and `DataHandlerLP`.
    The returned dataset can be used with qlib.contrib models.

    segments:
      train: [train_start, train_end]
      valid: (train_end, valid_end]
      test: (valid_end, test_end]
    """
    if not QLIB_DATA_AVAILABLE:
        raise RuntimeError("pyqlib is not installed or qlib.data modules are unavailable.")

    raw, features = _compute_features(bars)

    # qlib expects multi-index rows; columns may be multi-index with 'feature'/'label' top level.
    feature_cols = pd.MultiIndex.from_product([["feature"], features])
    label_cols = pd.MultiIndex.from_product([["label"], ["LABEL0"]])
    df = pd.concat(
        [
            raw[features].set_axis(feature_cols, axis=1),
            raw[["LABEL0"]].set_axis(label_cols, axis=1),
        ],
        axis=1,
    )

    loader = StaticDataLoader(df)
    handler = DataHandlerLP(
        data_loader=loader,
        infer_processors=[Fillna(fields_group="feature"), ZScoreNorm(fields_group="feature")],
        learn_processors=[DropnaLabel(), Fillna(fields_group="feature"), ZScoreNorm(fields_group="feature")],
    )

    dataset = DatasetH(
        handler,
        segments={
            "train": (train_start, train_end),
            "valid": (train_end, valid_end),
            "test": (valid_end, test_end),
        },
    )
    return QlibDatasetBundle(raw=df, dataset=dataset, handler=handler, features=features)
