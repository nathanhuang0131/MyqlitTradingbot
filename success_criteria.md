# Success Criteria - QlibTradingBot Quant-Fund Clean Mode

## 1) Hard Verification Gates
- [ ] `python -m pytest -q` passes.
- [ ] `python scripts/goalcheck.py` passes.

## 2) Qlib Core Architecture Exists and Imports
- [ ] `qlib_tradingbot/core/data_provider.py` exists and imports.
- [ ] `qlib_tradingbot/core/features.py` exists and imports.
- [ ] `qlib_tradingbot/core/qlib_signal_engine.py` exists and imports.
- [ ] `qlib_tradingbot/core/portfolio_risk.py` exists and imports.
- [ ] `qlib_tradingbot/core/execution_ledger.py` exists and imports.

## 3) Qlib Is Primary Signal Engine
- [ ] `QlibSignalEngine` outputs standardized SignalFrame columns:
  - `symbol`
  - `timestamp`
  - `alpha`
  - `direction`
  - `confidence`
  - `horizon`
  - `model_id`
- [ ] At least one strategy path (scalping) uses QlibSignalEngine ranking as primary selection.
- [ ] Rule-based logic is only post-filter after Qlib-ranked candidates.

## 4) Dry-Run Safety and Lazy Imports
- [ ] Unit tests and dry-run execution do not require `alpaca-py`.
- [ ] Alpaca imports are lazy and isolated in adapter code paths.
- [ ] Tests include a dry-run path asserting no alpaca import is needed.

## 5) Goalcheck Enforces Quant-Clean Gates
- [ ] Goalcheck verifies core modules exist and import.
- [ ] Goalcheck runs `QlibSignalEngine` in stub mode and creates a signals CSV.
- [ ] Goalcheck verifies `perf_report` output files (`pnl_daily.csv`, `win_rate.csv`).
- [ ] Goalcheck smoke-imports dashboard modules without requiring alpaca/qlib.

## 6) Streamlit Dashboards (Cached Data First)
- [ ] Entry point exists: `qlib_tradingbot/apps/dashboard_app.py`.
- [ ] Pages exist:
  - `qlib_tradingbot/dashboards/pages/1_Account.py`
  - `qlib_tradingbot/dashboards/pages/2_Market.py`
  - `qlib_tradingbot/dashboards/pages/3_FundFlows.py`
- [ ] Dashboards read from cached CSV in `Data/` and `Data/market/`.
- [ ] Missing files degrade gracefully with fallback UI text.

## 7) Model Registry Bootstrap
- [ ] `Data/model_registry/registry.json` exists.
- [ ] `Data/model_registry/model_cards/` exists.
- [ ] Strategy/horizon model selection is deterministic in tests with fixtures.

## 8) No-Network Tests
- [ ] New tests avoid network access.
- [ ] Fixtures/stubs for market and flow data exist under `Data/market/` and `Data/fixtures/`.
