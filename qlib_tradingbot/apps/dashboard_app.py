from __future__ import annotations

from importlib import import_module


def _st():
    try:
        return import_module("streamlit")
    except Exception:
        class _Dummy:
            def __getattr__(self, _name):
                def _noop(*_args, **_kwargs):
                    return None
                return _noop
        return _Dummy()


def main() -> None:
    st = _st()
    st.set_page_config(page_title="Qlib Trading Dashboard", layout="wide")
    st.title("Qlib Trading Dashboard")
    st.caption("Cached-data-first dashboard. Use streamlit run qlib_tradingbot/apps/dashboard_app.py")

    st.markdown("### Pages")
    st.write("1. Account & PnL")
    st.write("2. Market & Macro")
    st.write("3. Fund Flows")


if __name__ == "__main__":
    main()
