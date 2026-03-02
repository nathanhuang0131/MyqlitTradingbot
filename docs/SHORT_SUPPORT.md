# Short Support and Safety Gate

## Current Short Submission Path
- Strategy 4 emits short intents as `Signal(side="SELL", features.intent_order_type="BRACKET_SHORT")`.
- `Execution.engine.intent_from_signal()` converts this into `OrderIntent(order_type="BRACKET_SHORT")`.
- `Execution.engine.execute_intent()` routes to `Execution.orders.place_bracket_short()`.
- `place_bracket_short()` submits Alpaca market sell bracket order (sell-to-open short) when `DRY_RUN` is off.

## Account Capability Check
Preflight is implemented in `qlib_tradingbot/Execution/shorting.py`:
- Reads account via `alpaca_gateway.get_account(trade_client)`.
- Determines short support using the first available of:
  - `account.shorting_enabled`
  - `account.multiplier > 1` (margin)
  - `account.account_type in {margin, portfolio_margin}`

If unsupported and `allow_shorts=True` was requested:
- warning is logged/printed
- `allow_shorts` is forced to `False`
- short intents are skipped safely in `execute_signals(..., allow_shorts=False)`

## DRY_RUN Safety
`Execution/orders.py:_submit()` remains the final hard gate:
- `DRY_RUN=True` returns a dry-run payload and does not call broker submit.
- This behavior is unchanged by short preflight logic.
