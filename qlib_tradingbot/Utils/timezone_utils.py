from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


NY_TZ = ZoneInfo("America/New_York")
SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def to_new_york(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return dt.astimezone(NY_TZ)


def to_sydney(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return dt.astimezone(SYDNEY_TZ)


def _parse_hhmm(s: str) -> tuple[int, int]:
    h, m = str(s).split(":")
    return int(h), int(m)


def in_ny_trading_window(now_dt: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    ny_now = to_new_york(now_dt)
    sh, sm = _parse_hhmm(start_hhmm)
    eh, em = _parse_hhmm(end_hhmm)
    start_m = (sh * 60) + sm
    end_m = (eh * 60) + em
    now_m = (ny_now.hour * 60) + ny_now.minute
    return start_m <= now_m <= end_m


def format_session_window(now_dt: datetime, start_hhmm: str, end_hhmm: str) -> str:
    ny_now = to_new_york(now_dt)
    sy_now = to_sydney(now_dt)
    return (
        f"Session window (New York): {start_hhmm}-{end_hhmm} | "
        f"Now New York: {ny_now.strftime('%Y-%m-%d %H:%M:%S %Z')} | "
        f"Now Sydney: {sy_now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )
