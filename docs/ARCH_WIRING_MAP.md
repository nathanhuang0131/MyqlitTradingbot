# Architecture Wiring Map

## Entrypoints
- `main.py` calls `qlib_tradingbot.UI.cli.run_once_interactive()`.
- Interactive CLI builds runtime config and repeatedly invokes orchestrator in loop mode.

## Strategy 4 (Scalping) Exact Call Flow
1. `main.py` -> `run_once_interactive()`
2. `run_once_interactive()`:
- creates Alpaca clients via `build_clients(paper=PAPER)`
- builds `cfg` and `StrategyContext`
- calls `Orchestrator.run_once(strategy_name, ctx)`
3. `Orchestrator.run_once()`:
- checks market status via `get_market_clock(ctx.trade_client)`
- if open, calls `StrategyDispatcher.run(strategy_name, ctx)`
4. `StrategyDispatcher.run()`:
- `build()` from registry -> `ScalpingStrategy`
- `build_universe()`
- `prepare_features()`
- `generate_signals()`
- `execute()`
- `post_trade_reporting()`
5. `ScalpingStrategy` internals:
- `build_universe()` runs `run_3stage_qlib_scalp_pipeline()` and reads `Data/universe_trade_today.csv`
- `prepare_features()` runs `stage3_qlib_score()` + `fetch_1m_bars_batch()`
- `generate_signals()` calls `signals_from_bias_and_1m_trigger(..., allow_shorts=ctx.config.get("allow_shorts", False))`
- `execute()` calls `Execution.engine.execute_signals()`
6. `Execution.engine.execute_signals()`:
- converts `Signal` -> `OrderIntent`
- routes to `Execution.orders` helpers (`place_bracket_buy`, `place_bracket_short`, etc.)
7. `Execution.orders`:
- `_submit()` enforces `DRY_RUN` (no broker submit when enabled)
- appends audit logs via `Data/logs.py` (`trade_attempts.csv`, `order_events.csv`)

## Config Flow (CLI -> Strategy -> Execution)
- CLI reads user input and constructs `cfg` dict in `qlib_tradingbot/UI/cli.py`.
- `cfg` is attached to `StrategyContext.config`.
- Strategy reads values directly from `self.ctx.config` (`top_n_signals`, windows, etc.).
- Execution receives only generated `Signal` objects; execution hints are passed through `Signal.features` (e.g. `intent_order_type`).

## Runtime Gates and Modes
- `PAPER` and `DRY_RUN` are loaded in `qlib_tradingbot/config.py` from env vars.
- `PAPER` is used when building clients (`build_clients(paper=PAPER)`).
- `DRY_RUN` is enforced at order submit layer (`Execution/orders.py:_submit`).
- Market-closed behavior lives in `Orchestrator._market_open_or_skip()`; returns `market_closed` status when closed.
- Loop behavior lives in CLI `while True`; when `loop_mode=True`, the CLI sleeps and retries each cycle.

## Existing Trade History / Logs / Analytics
- Existing CSV/JSON outputs:
- `Data/orders.csv`
- `Data/signals.csv`
- `Data/positions_snapshots.csv`
- `Data/run_log.jsonl`
- `Data/trade_attempts.csv`
- `Data/order_events.csv`
- Existing analytics helpers in `qlib_tradingbot/Reporting/reporting.py`:
- `compute_pnl_daily()`
- `write_pnl_daily_csv()`
- `write_win_rate_csv()`

## Best Hook Points

### 1) `allow_shorts`
- CLI input: `qlib_tradingbot/UI/cli.py` near strategy selection and cfg construction.
- Strategy plumbing: `ScalpingStrategy.generate_signals()` already consumes `ctx.config["allow_shorts"]`.
- Safety override hook: preflight in execution path (engine/orchestrator) before `place_bracket_short` can be called.

### 2) Analytics (ledger + derived reports)
- Ledger append hook: `Orchestrator.run_once()` after `execution_result` is available and position snapshots are fetched.
- Read/compute module: new `qlib_tradingbot/Analytics/performance.py` with pure functions.
- CLI display hook: new analytics menu branch in `run_once_interactive()` that does not depend on market open.

### 3) LLM gating and post-market review
- Export generation hook:
- manual CLI action for market-closed operation
- optional orchestrator path after run / market close
- Feedback state load/apply hook:
- parse feedback in new `qlib_tradingbot/LLM/feedback_handler.py`
- apply filter/resize inside `ScalpingStrategy.generate_signals()` before `execute()`.

## Key Constraints to Preserve
- Do not alter behavior of strategies 1-4 unless config explicitly enables new behavior.
- Keep paper trading defaults (`PAPER=True` by default env config).
- Keep `DRY_RUN` hard safety (no submit).
