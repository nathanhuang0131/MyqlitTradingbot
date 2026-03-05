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
1. Execute `G5-A`: intraday_3alpha strategy + feature builder + qlib stub integration.
2. Execute `G5-B`: automatic intraday runner + outputs + LLM bias gating.
3. Execute `G5-C`: dashboard alpha columns + goalcheck + tests.

### Phase 5: Intraday 3-Alpha Autonomy
- [x] G5-A: Add `intraday_3alpha` with blended alpha:
  - `alpha_total = 0.55*alpha_ml + 0.25*alpha_mr + 0.20*alpha_mom`
  - 15-feature intraday builder with `label_fwd_ret_6`
  - QlibSignalEngine `--strategy intraday_3alpha` predict path (stub-safe)
- [x] G5-B: Add unattended runner command:
  - `python -m qlib_tradingbot.apps.cli_app --strategy intraday_3alpha --mode loop --rebalance-min 15 --ny-window 09:30-15:55 --paper`
  - market-closed sleep/retry behavior
  - output files under `Data/signals`, `Data/intents`, `Data/trade_history`, `Data/performance`
- [x] G5-C: Add tests + goalcheck enforcement for intraday 3-alpha and dashboard alpha columns.
