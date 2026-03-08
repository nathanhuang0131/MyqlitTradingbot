from __future__ import annotations

from importlib import import_module
import os

render = import_module("qlib_tradingbot.dashboards.pages.2_Market").render


def main() -> None:
    render()


if __name__ == "__main__" and "PYTEST_CURRENT_TEST" not in os.environ:
    main()
