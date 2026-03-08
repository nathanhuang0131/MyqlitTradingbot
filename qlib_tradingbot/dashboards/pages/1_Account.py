from __future__ import annotations

from pathlib import Path

from qlib_tradingbot.dashboards.data_views import load_account_view


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


def _fmt(value):
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return str(value)


def render(data_root: Path | str = "Data") -> None:
    st = _st()
    view = load_account_view(Path(data_root))
    m = view["metrics"]

    st.header("Account Operations")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Equity", _fmt(m["equity"]))
    c2.metric("Cash", _fmt(m["cash"]))
    c3.metric("Buying Power", _fmt(m["buying_power"]))
    c4.metric("Open Positions", _fmt(m["open_positions"]))
    c5.metric("Pending Orders", _fmt(m["pending_orders"]))

    c6, c7, c8, c9 = st.columns(4)
    c6.metric("Realized PnL (Daily)", _fmt(m["realized_pnl_daily"]))
    c7.metric("Unrealized PnL", _fmt(m["unrealized_pnl"]))
    c8.metric("Total PnL", _fmt(m["total_pnl"]))
    c9.metric("Win Rate", _fmt(m["win_rate"]))

    c10, c11, c12, c13 = st.columns(4)
    c10.metric("Market Open", _fmt(m["market_open"]))
    c11.metric("Within Window", _fmt(m["within_window"]))
    c12.metric("Dry Run", _fmt(m["dry_run"]))
    c13.metric("Broker Configured", _fmt(m["broker_configured"]))
    st.caption(f"Last run id: {m.get('last_run_id') or 'n/a'}")

    pnl_daily = view["pnl_daily"]
    if not pnl_daily.empty and {"day", "net_pnl"}.issubset(pnl_daily.columns):
        st.subheader("PnL Line")
        st.line_chart(pnl_daily.set_index("day")["net_pnl"])
    elif not pnl_daily.empty:
        st.subheader("PnL Line")
        st.line_chart(pnl_daily.set_index(pnl_daily.columns[0])[pnl_daily.columns[1]])
    else:
        st.info("No cached pnl series found at Data/performance/pnl_daily.csv")

    st.subheader("Recent Fills / Orders")
    recent = view["recent_orders"]
    if recent.empty:
        st.info("No cached fills/orders found.")
    else:
        st.dataframe(recent.tail(50), use_container_width=True)

    st.subheader("Exposure")
    exposure = view["exposure"]
    if exposure.empty:
        st.info("No cached exposure data available yet.")
    else:
        st.dataframe(exposure, use_container_width=True)


render()

