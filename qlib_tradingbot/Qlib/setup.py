from __future__ import annotations

from pathlib import Path
from typing import Optional

from qlib_tradingbot.config import QLIB_PROVIDER_URI, QLIB_REGION

try:  # pragma: no cover
    import qlib
    from qlib.config import REG_CN, REG_US
    QLIB_AVAILABLE = True
except Exception:  # pragma: no cover
    qlib = None  # type: ignore
    REG_CN = REG_US = None  # type: ignore
    QLIB_AVAILABLE = False


def init_qlib(provider_uri: Optional[str] = None, region: Optional[str] = None) -> None:
    """Initialize qlib global config.

    This is safe to call multiple times in a process.
    """
    if not QLIB_AVAILABLE:
        raise RuntimeError("pyqlib is not installed. Install with: pip install pyqlib==0.9.7")

    provider_uri = provider_uri or QLIB_PROVIDER_URI
    region = (region or QLIB_REGION).lower().strip()
    if region == "us":
        qlib.init(provider_uri=str(provider_uri), region=REG_US)
    elif region == "cn":
        qlib.init(provider_uri=str(provider_uri), region=REG_CN)
    else:
        raise ValueError(f"Unsupported QLIB_REGION={region!r}; expected 'us' or 'cn'")
