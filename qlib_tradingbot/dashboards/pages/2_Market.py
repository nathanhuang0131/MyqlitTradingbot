from __future__ import annotations

from pathlib import Path

import pandas as pd

from qlib_tradingbot.core.data_provider import DataProvider


MACRO_SYMBOLS = ["US10Y", "DXY", "GOLD", "SILVER", "BTC", "SPY", "QQQ", "OEF"]


def _st():
    try:
        import streamlit as st
        return st
    except Exception:
        class _Dummy:
            def __getattr__(self, _name):
                def _noop(*_args, **_kwargs):
                    return None
                return _noop
        return _Dummy()


def render(data_root: Path | str = "Data") -> None:
    st = _st()
    root = Path(data_root)
    provider = DataProvider(data_root=root)

    st.header("Market & Macro")
    if st.button("Refresh"):
        provider.refresh_market_cache(MACRO_SYMBOLS)

    for sym in MACRO_SYMBOLS:
        df = provider.read_market_series(sym)
        st.subheader(sym)
        if df.empty:
            st.caption(f"Missing cached series for {sym} at Data/market/{sym}.csv")
        else:
            st.dataframe(df.tail(30))

    sig_path = root / "signals" / "intraday_3alpha_signals.csv"
    if sig_path.exists():
        sig = pd.read_csv(sig_path)
        st.subheader("Intraday Alphas")
        cols = [c for c in ["symbol", "alpha_ml", "alpha_mr", "alpha_mom", "alpha_total", "close_last", "dollar_vol"] if c in sig.columns]
        if cols:
            st.dataframe(sig[cols].head(50))
        else:
            st.dataframe(sig.head(50))
            st.caption("Missing expected alpha columns in cached signals file.")

        if {"symbol", "close_last"}.issubset(sig.columns):
            watch = sig.copy()
            watch["move_pct"] = pd.to_numeric(watch.get("intraday_return", 0.0), errors="coerce").fillna(0.0) * 100.0
            wcols = [c for c in ["symbol", "close_last", "dollar_vol", "vol_ratio_1", "move_pct"] if c in watch.columns]
            if wcols:
                st.subheader("Watchlist Price/Volume/Move")
                st.dataframe(watch[wcols].head(50))


render()
