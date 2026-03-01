
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

try:  # pragma: no cover
    import lightgbm as lgb
    LGB_OK = True
except Exception:  # pragma: no cover
    lgb = None
    LGB_OK = False


@dataclass
class SimpleLGBMBundle:
    features: pd.DataFrame  # multi-index (datetime, symbol)
    label: pd.Series        # aligned with features index
    feature_names: list[str]


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    # Wilder's smoothing
    roll_up = up.ewm(alpha=1/period, adjust=False).mean()
    roll_down = down.ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _atr(df_sym: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df_sym["high"]
    low = df_sym["low"]
    close = df_sym["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def build_features_and_label(
    bars: pd.DataFrame,
    *,
    horizon_bars: int = 3,
) -> SimpleLGBMBundle:
    """
    Build a compact, 'scalp-friendly' feature set on 5m bars and a forward-return label.

    Input bars columns: symbol, datetime (tz-aware), open, high, low, close, volume
    Output:
      features index: MultiIndex(datetime, symbol)
      label: forward_return over horizon_bars (close[t+h]/close[t]-1)
    """
    if bars is None or bars.empty:
        raise ValueError("bars is empty")

    df = bars.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.sort_values(["symbol", "datetime"])

    out_frames = []
    for sym, g in df.groupby("symbol", sort=False):
        g = g.sort_values("datetime").copy()

        close = g["close"].astype(float)
        vol = g["volume"].astype(float)

        # returns
        g["ret1"] = close.pct_change(1)
        g["ret3"] = close.pct_change(3)
        g["ret6"] = close.pct_change(6)

        # momentum / trend
        g["ema12"] = close.ewm(span=12, adjust=False).mean()
        g["ema26"] = close.ewm(span=26, adjust=False).mean()
        g["macd"] = g["ema12"] - g["ema26"]
        g["macd_sig"] = g["macd"].ewm(span=9, adjust=False).mean()
        g["macd_hist"] = g["macd"] - g["macd_sig"]

        # vol / range
        g["atr14"] = _atr(g, 14)
        g["hl_range"] = (g["high"] - g["low"]) / close.replace(0.0, np.nan)

        # oscillator
        g["rsi14"] = _rsi(close, 14)

        # volume normalization per symbol
        g["vol_z"] = (vol - vol.rolling(78, min_periods=10).mean()) / (
            vol.rolling(78, min_periods=10).std().replace(0.0, np.nan)
        )

        # label: forward return
        g["y"] = close.shift(-horizon_bars) / close - 1.0

        out_frames.append(g)

    feat_cols = ["ret1","ret3","ret6","macd","macd_hist","atr14","hl_range","rsi14","vol_z"]
    
full = pd.concat(out_frames, axis=0, ignore_index=True)

# diagnostics before dropping NaNs (helps understand why training becomes degenerate)
diag_nan_rate = full[feat_cols + ["y"]].isna().mean(numeric_only=False) if len(full) else pd.Series(dtype=float)
diag_total_rows = int(len(full))
diag_total_symbols = int(full["symbol"].nunique()) if "symbol" in full.columns else 0

# drop unusable rows (NaNs from indicators/label) (NaNs from indicators/label)
    full = full.dropna(subset=feat_cols + ["y"]).copy()

    # MultiIndex expected by the rest of the bot
    full = full.set_index(["datetime","symbol"]).sort_index()

    
X = full[feat_cols].astype(float)
y = full["y"].astype(float)

# more diagnostics after cleaning
try:
    sym_counts = (
        full.reset_index()
        .groupby("symbol")["datetime"]
        .agg(["count", "min", "max"])
        .rename(columns={"count": "n_rows", "min": "start_dt", "max": "end_dt"})
        .sort_values("n_rows", ascending=False)
        .reset_index()
    )
except Exception:
    sym_counts = None

diagnostics = {
    "total_rows_raw": diag_total_rows,
    "total_symbols_raw": diag_total_symbols,
    "rows_after_dropna": int(len(full)),
    "symbols_after_dropna": int(full.reset_index()["symbol"].nunique()) if len(full) else 0,
    "label_mean": float(np.nanmean(y.values)) if len(y) else float("nan"),
    "label_std": float(np.nanstd(y.values)) if len(y) else float("nan"),
    "label_min": float(np.nanmin(y.values)) if len(y) else float("nan"),
    "label_p05": float(np.nanpercentile(y.values, 5)) if len(y) else float("nan"),
    "label_p50": float(np.nanpercentile(y.values, 50)) if len(y) else float("nan"),
    "label_p95": float(np.nanpercentile(y.values, 95)) if len(y) else float("nan"),
    "label_max": float(np.nanmax(y.values)) if len(y) else float("nan"),
}

return SimpleLGBMBundle(
    features=X,
    label=y,
    feature_names=feat_cols,
    diagnostics=diagnostics,
    feature_nan_rate=diag_nan_rate,
    per_symbol=sym_counts,
)


def train_simple_lgbm(
    bundle: SimpleLGBMBundle,
    *,
    params: Optional[Dict] = None,
) -> "lgb.Booster":
    """Train a LightGBM regressor on the engineered 5m features."""
    if not LGB_OK:
        raise RuntimeError("lightgbm is not installed in this environment")

    X = bundle.features
    y = bundle.label

    # Guard: if label is nearly constant, LGBM will not split and will spam warnings
    if float(np.nanstd(y.values)) < 1e-8:
        raise RuntimeError("Label variance is ~0; cannot train a meaningful model. Increase lookback or horizon.")

    default = dict(
        objective="regression",
        learning_rate=0.05,
        num_leaves=31,
        min_data_in_leaf=50,
        feature_fraction=0.9,
        bagging_fraction=0.9,
        bagging_freq=1,
        num_threads=0,
        verbosity=-1,
    )
    if params:
        default.update(params)

    dtrain = lgb.Dataset(X.values, label=y.values, feature_name=bundle.feature_names)
    booster = lgb.train(default, dtrain, num_boost_round=200)
    return booster


def predict_simple_lgbm(model: "lgb.Booster", bundle: SimpleLGBMBundle) -> pd.Series:
    """Return predictions as a Series indexed by (datetime, symbol)."""
    X = bundle.features
    preds = model.predict(X.values)
    return pd.Series(preds, index=X.index, name="pred")



def write_training_diagnostics(
    bundle: SimpleLGBMBundle,
    *,
    out_dir: "Path",
    prefix: str = "stage3_simple_lgbm",
) -> None:
    """Write training dataset diagnostics to CSV files.

    Produces:
      - <prefix>_summary_<ts>.csv (key/value)
      - <prefix>_feature_nan_<ts>.csv (feature, nan_rate)
      - <prefix>_symbol_samples_<ts>.csv (symbol, n_rows, start_dt, end_dt)
    """
    from pathlib import Path
    import datetime as _dt

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # summary
    summary_path = Path(out_dir) / f"{prefix}_summary_{ts}.csv"
    diag = bundle.diagnostics or {}
    df_sum = pd.DataFrame([{"key": k, "value": v} for k, v in diag.items()])
    df_sum.to_csv(summary_path, index=False)

    # feature nan rate (pre-dropna)
    if bundle.feature_nan_rate is not None and len(bundle.feature_nan_rate):
        fn_path = Path(out_dir) / f"{prefix}_feature_nan_{ts}.csv"
        pd.DataFrame(
            {"feature": bundle.feature_nan_rate.index.astype(str), "nan_rate": bundle.feature_nan_rate.values}
        ).to_csv(fn_path, index=False)

    # per-symbol sample counts
    if bundle.per_symbol is not None and len(bundle.per_symbol):
        sym_path = Path(out_dir) / f"{prefix}_symbol_samples_{ts}.csv"
        bundle.per_symbol.to_csv(sym_path, index=False)