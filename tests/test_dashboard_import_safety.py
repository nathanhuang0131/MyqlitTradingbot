from __future__ import annotations

import importlib
import os


def test_dashboard_pages_import_without_auto_render(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    modules = [
        "qlib_tradingbot.dashboards.pages.1_Account",
        "qlib_tradingbot.dashboards.pages.2_Market",
        "qlib_tradingbot.dashboards.pages.3_FundFlows",
        "qlib_tradingbot.apps.pages.1_Account",
        "qlib_tradingbot.apps.pages.2_Market",
        "qlib_tradingbot.apps.pages.3_FundFlows",
    ]
    for mod in modules:
        m = importlib.import_module(mod)
        assert hasattr(m, "render") or hasattr(m, "main")

