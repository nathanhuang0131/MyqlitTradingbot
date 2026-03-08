# Changelog

## 2026-03-08

- Added `qlib_tradingbot.bootstrap.settings` for automatic `.env` bootstrap, key alias normalization, and broker validation helpers.
- Refactored broker wiring to provide explicit diagnostics via `diagnose_broker_setup` and actionable `BrokerClientError`.
- Added broker diagnostic command: `python scripts/diagnose_broker.py`.
- Removed hard dependency on alpaca request classes for fake-client submit paths by introducing `Execution/order_adapter.py`.
- Standardized imports to `qlib_tradingbot.core` convention.
- Upgraded Streamlit dashboards into cached-data-first operations pages with richer cards/tables and clear empty states.
- Updated README with `.env` formats, troubleshooting, and dashboard usage guidance.
- Added tests for settings/bootstrap, broker diagnostics, and non-dry-run fake-client order submission.

