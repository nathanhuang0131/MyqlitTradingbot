from __future__ import annotations

from pathlib import Path

from qlib_tradingbot.dashboards.data_views import load_fund_flows_view


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
    view = load_fund_flows_view(Path(data_root))

    st.header("Fund Flows")
    st.info(view["risk_box"])
    st.info(view["rotation_box"])

    st.subheader("Flow Proxies")
    if view["flows"].empty:
        st.info("No cached flow proxy file found at Data/market/fund_flows_proxy.csv")
    else:
        st.dataframe(view["flows"].tail(200), use_container_width=True)

    st.subheader("Positioning Proxies")
    if view["positioning"].empty:
        st.info("No cached positioning proxy file found at Data/market/positioning_proxy.csv")
    else:
        st.dataframe(view["positioning"].tail(200), use_container_width=True)


render()

