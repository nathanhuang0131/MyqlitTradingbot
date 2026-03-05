from __future__ import annotations

import sys

__version__ = "1.0.0"

# Windows repo history uses `Core/`; expose lowercase alias required by new architecture docs.
try:
    from . import Core as _core_pkg

    sys.modules.setdefault("qlib_tradingbot.core", _core_pkg)
    core = _core_pkg
except Exception:
    pass
