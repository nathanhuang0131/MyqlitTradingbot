name: dashboard_ops
description: Build operations-grade dashboards with cached-data-first behavior and clear risk/action visibility.
steps:
  - Add account/market/flows/position-trace operational cards and tables.
  - Show decision funnel (qlib -> llm -> risk -> execution) from cached traces.
  - Surface blocked trades, alerts, and broker/session health.
  - Ensure all pages degrade gracefully when cache files are missing.
  - Prevent import-time side effects during tests.

