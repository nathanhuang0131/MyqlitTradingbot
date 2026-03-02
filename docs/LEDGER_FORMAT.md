# Trade Ledger Format

Path: `Data/trades_ledger.csv`

This ledger is append-only and records best-available execution outcomes per run.

## Columns
- `timestamp`: UTC ISO timestamp for ledger append event
- `strategy`: strategy name
- `symbol`: ticker symbol
- `side`: execution action / side
- `qty`: filled or requested quantity (if available)
- `fill_price`: fill price (if available)
- `order_id`: broker order id (if available)
- `event`: `OPEN` or `CLOSE`
- `realized_pnl`: realized profit/loss (if available)
- `fees`: fees/commissions (if available)
- `tags`: free text tags (error/status notes)

## Notes
- Existing execution outputs do not always include true fill-level fields; missing values remain blank.
- Analytics functions treat missing `realized_pnl`/`fees` as `0.0`.
- The file schema is auto-healed on write if older columns are missing.
