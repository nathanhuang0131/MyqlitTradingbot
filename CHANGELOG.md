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
- Added governed qlib+llm decision fusion modules under `qlib_tradingbot/Decision/` (typed models, policy rules, fusion records).
- Added world-class traceability outputs: `decision_trace.jsonl`, `position_journal.csv`, `position_health.csv`.
- Added execution guardrail checks for non-dry-run paths (broker/client/daily-loss/exposure/trace-write gating).
- Added Position Trace dashboard page plus signal-funnel/model-attribution operational views.
- Updated dashboard pages to avoid auto-render side effects during test imports.
- Added deterministic offline tests for decision fusion, traceability persistence/review, guardrail blocking, and dashboard import safety.
- Added direct unit coverage for `fuse_signals` and expanded decision trace provenance (`qlib_rank`, `qlib_horizon`, `llm_action`, `risk_state`) for stronger auditability.
- Hardened position journal upsert logic to avoid pandas concat deprecation paths when appending first rows.
- Improved manual LLM workflow ergonomics: generated `feedback_template.csv` now ships with safe defaults (`Neutral`, `50`, `Hold`) and docs now include explicit offline pack->ingest steps.
