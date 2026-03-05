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

    sig_path = root / "signals.csv"
    if sig_path.exists():
        sig = pd.read_csv(sig_path)
        st.subheader("Per-Symbol Signals")
        st.dataframe(sig.tail(50))


render()
