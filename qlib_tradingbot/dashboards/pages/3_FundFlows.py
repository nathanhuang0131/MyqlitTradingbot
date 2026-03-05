from __future__ import annotations

from pathlib import Path

import pandas as pd


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
    st.header("Fund Flows")

    flow_path = root / "market" / "fund_flows_proxy.csv"
    pos_path = root / "market" / "positioning_proxy.csv"

    flows = pd.read_csv(flow_path) if flow_path.exists() else pd.DataFrame()
    pos = pd.read_csv(pos_path) if pos_path.exists() else pd.DataFrame()

    if flows.empty and pos.empty:
        st.info("No cached flow/positioning proxies found. Expected Data/market/fund_flows_proxy.csv and positioning_proxy.csv")
        return

    if not flows.empty:
        st.subheader("Flow Proxies")
        st.dataframe(flows.tail(100))

    if not pos.empty:
        st.subheader("Positioning Proxies")
        st.dataframe(pos.tail(100))


render()
