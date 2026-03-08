from __future__ import annotations

from importlib import import_module
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # project root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    st.set_page_config(page_title="Qlib Operations Dashboard", layout="wide")
    st.title("Qlib Operations Dashboard")
    st.caption("Cached-data-first control center. Use streamlit run qlib_tradingbot/apps/dashboard_app.py")

    st.markdown("### Pages")
    st.write("1. Account Operations")
    st.write("2. Market Operations")
    st.write("3. Fund Flows")


if __name__ == "__main__":
    main()
