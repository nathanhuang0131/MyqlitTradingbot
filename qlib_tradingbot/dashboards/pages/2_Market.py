from __future__ import annotations

import os
from pathlib import Path

from qlib_tradingbot.dashboards.data_views import MACRO_SYMBOLS, load_market_view


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


def _fmt(value, *, pct: bool = False) -> str:
    if value is None:
        return "n/a"
    if pct:
        return f"{float(value):.2f}%"
    return f"{float(value):,.2f}"


def render(data_root: Path | str = "Data") -> None:
    st = _st()
    view = load_market_view(Path(data_root))

    st.header("Market Operations")
    macro = view["macro"]
    if macro.empty:
        st.info("No macro cache found under Data/market.")
    else:
        cols = st.columns(len(MACRO_SYMBOLS))
        for i, sym in enumerate(MACRO_SYMBOLS):
            row = macro[macro["symbol"] == sym]
            close = row["close"].iloc[0] if not row.empty else None
            move = row["move_pct"].iloc[0] if not row.empty else None
            cols[i].metric(sym, _fmt(close), delta=_fmt(move, pct=True) if move is not None else None)

    st.subheader("Top Movers / Watchlist")
    movers = view["top_movers"]
    if movers.empty:
        st.info("No cached watchlist mover data available.")
    else:
        st.dataframe(movers, use_container_width=True)

    st.subheader("Alpha Decomposition")
    alpha = view["alpha"]
    if alpha.empty:
        st.info("No cached alpha decomposition found (expected alpha_ml/alpha_mr/alpha_mom/alpha_total).")
    else:
        st.dataframe(alpha.head(100), use_container_width=True)

    st.subheader("Stage Funnel")
    funnel = view["stage_funnel"]
    if funnel.empty:
        st.info("No stage trace funnel available. Expected Data/stage_trace.csv.")
    else:
        st.dataframe(funnel, use_container_width=True)

    st.subheader("Model Attribution")
    attrib = view.get("model_attribution")
    if attrib is None or attrib.empty:
        st.info("No model attribution available from cached alpha data.")
    else:
        st.dataframe(attrib, use_container_width=True)

    st.subheader("Signal Funnel (qlib -> llm -> risk -> execution)")
    sig_funnel = view.get("signal_funnel")
    if sig_funnel is None or sig_funnel.empty:
        st.info("No cached signal funnel trace available.")
    else:
        st.dataframe(sig_funnel, use_container_width=True)


def main() -> None:
    render()


if __name__ == "__main__" and "PYTEST_CURRENT_TEST" not in os.environ:
    main()
