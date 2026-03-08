from __future__ import annotations

import json
from typing import Any

from qlib_tradingbot.Brokers.alpaca_clients import diagnose_broker_setup


def broker_diagnostic_report(*, paper: bool | None = None, try_build: bool = True) -> dict[str, Any]:
    return diagnose_broker_setup(paper=paper, try_build=try_build)


def format_broker_diagnostic(*, paper: bool | None = None, try_build: bool = True) -> str:
    report = broker_diagnostic_report(paper=paper, try_build=try_build)
    return json.dumps(report, indent=2, default=str)

