from __future__ import annotations

import os
from pathlib import Path

from qlib_tradingbot.dashboards.data_views import load_position_trace_view


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
    view = load_position_trace_view(Path(data_root))
    st.header("Position Trace")

    merged = view["merged"]
    if merged.empty:
        st.info("No open position trace found. Expected Data/position_journal.csv and Data/position_health.csv.")
    else:
        st.subheader("Open Positions / Thesis State")
        st.dataframe(merged.tail(200), use_container_width=True)

    trace = view["trace"]
    st.subheader("Latest Recommendations")
    if trace.empty:
        st.info("No decision trace found at Data/decision_trace.jsonl")
    else:
        cols = [c for c in ["ts_utc", "symbol", "strategy_id", "model_id", "qlib_alpha", "qlib_confidence", "llm_bias", "llm_probability", "final_action", "blocked", "reasons"] if c in trace.columns]
        st.dataframe(trace[cols].tail(200) if cols else trace.tail(200), use_container_width=True)


def main() -> None:
    render()


if __name__ == "__main__" and "PYTEST_CURRENT_TEST" not in os.environ:
    main()

