from __future__ import annotations

import os
from importlib import import_module

render = import_module("qlib_tradingbot.dashboards.pages.4_PositionTrace").render


def main() -> None:
    render()


if __name__ == "__main__" and "PYTEST_CURRENT_TEST" not in os.environ:
    main()

