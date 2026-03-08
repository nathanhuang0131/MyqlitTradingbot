from __future__ import annotations

import pandas as pd


def build_price_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["timestamp", "ret_1", "ret_5", "vol_z", "dollar_vol"])

    out = df.copy()
    if "timestamp" not in out.columns and "datetime" in out.columns:
        out = out.rename(columns={"datetime": "timestamp"})
    out["close"] = pd.to_numeric(out.get("close", 0.0), errors="coerce").fillna(0.0)
    out["volume"] = pd.to_numeric(out.get("volume", 0.0), errors="coerce").fillna(0.0)

    out["ret_1"] = out["close"].pct_change().fillna(0.0)
    out["ret_5"] = out["close"].pct_change(5).fillna(0.0)
    vol_mean = out["volume"].rolling(20).mean().fillna(out["volume"].mean() if len(out) else 0.0)
    vol_std = out["volume"].rolling(20).std().replace(0, pd.NA)
    out["vol_z"] = ((out["volume"] - vol_mean) / vol_std).fillna(0.0)
    out["dollar_vol"] = out["close"] * out["volume"]

    cols = [c for c in ["timestamp", "ret_1", "ret_5", "vol_z", "dollar_vol"] if c in out.columns]
    return out[cols].copy()


__all__ = ["build_price_volume_features"]
