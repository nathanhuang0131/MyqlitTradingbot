from __future__ import annotations

from pathlib import Path

import pandas as pd


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


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
    st.header("Account & PnL")

    orders = _read(root / "orders.csv")
    pnl_daily = _read(root / "performance" / "pnl_daily.csv")
    win_rate = _read(root / "performance" / "win_rate.csv")

    if orders.empty:
        st.info("No cached account/order data found. Use Refresh to populate Data/*.csv")
    else:
        st.dataframe(orders.tail(50))

    if not pnl_daily.empty:
        st.subheader("Daily PnL")
        st.line_chart(pnl_daily.set_index(pnl_daily.columns[0])[pnl_daily.columns[1]])

    if not win_rate.empty:
        st.subheader("Win Rate")
        st.dataframe(win_rate.tail(30))


render()
