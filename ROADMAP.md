# ROADMAP: Quant-Fund Clean Mode

## Mission
Refactor the bot to a clean architecture where Qlib is the core alpha engine, paper trading is default-safe, and Streamlit dashboards run from cached data.

## Non-Negotiables
- [ ] `python -m pytest -q` passes
- [ ] `python scripts/goalcheck.py` passes
- [ ] `success_criteria.md` satisfied
- [ ] No network calls in unit tests
- [ ] Dry-run/test paths do not require `alpaca-py`
- [ ] Live trading requires explicit `--live` and config allowlist

## Operating Loop
1. Pick smallest unchecked gate.
2. Update `success_criteria.md` for that gate.
3. Update `scripts/goalcheck.py` to enforce the gate (fail first).
4. Implement minimal code + tests.
5. Run `python -m pytest -q` and `python scripts/goalcheck.py`.
6. Mark gate complete.

## Gate Plan

### Phase 3: Qlib Core Integration
- [x] G3-A: Add 5-file core architecture scaffolding:
  - `qlib_tradingbot/core/data_provider.py`
  - `qlib_tradingbot/core/features.py`
  - `qlib_tradingbot/core/qlib_signal_engine.py`
  - `qlib_tradingbot/core/portfolio_risk.py`
  - `qlib_tradingbot/core/execution_ledger.py`
- [x] G3-B: QlibSignalEngine stub mode + goalcheck gate.
  - Must emit standardized SignalFrame columns:
    `symbol,timestamp,alpha,direction,confidence,horizon,model_id`
  - Must support CLI stub output to CSV.
  - Must import/run without pyqlib installed.
- [x] G3-C: Convert one strategy (scalping) end-to-end to QlibSignalEngine-first ranking.
  - Qlib ranking is primary.
  - Rule logic remains only as post-filter.
- [ ] G3-D: Dry-run/lazy Alpaca import hardening and test coverage.
  - No `alpaca-py` dependency for unit tests, goalcheck, dashboard imports.

### Phase 4: Dashboard + Registry + Backtest
- [ ] G4-A: Add model registry structure and deterministic selection.
  - `Data/model_registry/registry.json`
  - `Data/model_registry/model_cards/*`
- [ ] G4-B: Add minimal backtest path using provider -> features -> qlib -> portfolio -> ledger.
- [ ] G4-C: Streamlit app skeleton + 3 pages (Account, Market, Fund Flows).
  - `qlib_tradingbot/apps/dashboard_app.py`
  - `qlib_tradingbot/dashboards/pages/1_Account.py`
  - `qlib_tradingbot/dashboards/pages/2_Market.py`
  - `qlib_tradingbot/dashboards/pages/3_FundFlows.py`
  - Must read cached CSV from `Data/` and `Data/market/`.
- [ ] G4-D: Fund flow stubs + ingestion script path from cached CSVs.
- [ ] G4-E: Goalcheck/dashboard smoke imports + performance report file checks.

## Immediate Work Order
1. Execute `G3-B`.
2. Execute `G3-C`.
