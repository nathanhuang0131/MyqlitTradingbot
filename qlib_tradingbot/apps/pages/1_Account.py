from __future__ import annotations

from importlib import import_module

render = import_module("qlib_tradingbot.dashboards.pages.1_Account").render

render()
