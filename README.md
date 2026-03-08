# QlibTradingbot Unified Strategy Runner

Unified strategy system with Alpaca integration, Qlib-informed scoring, NY-time trading windows, and CSV-first reporting.

## Architecture (Qlib-First + Governed LLM)

- Qlib remains the primary ranking/signal engine.
- LLM is a governed decision-assist layer (not autonomous free-form execution).
- Decision fusion evaluates qlib signal strength, LLM bias/probability, and risk state to produce: `buy`, `sell`, `reduce`, `hold`, or `block`.
- Non-dry-run orders pass execution guardrails before submit.
- Every decision and open-position state is persisted for traceability.

## Windows (Conda) setup

```powershell
conda create -n qlibtradingbot python=3.11 -y
conda activate qlibtradingbot
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Broker Configuration (.env or environment variables)

The app now auto-loads `.env` from the project root at startup.

Supported key names (either scheme works):

```dotenv
# Canonical
APCA_API_KEY_ID=YOUR_KEY
APCA_API_SECRET_KEY=YOUR_SECRET

# Alternate aliases (also supported)
ALPACA_API_KEY=YOUR_KEY
ALPACA_SECRET_KEY=YOUR_SECRET

APCA_API_BASE_URL=https://paper-api.alpaca.markets
ALPACA_PAPER=1
DRY_RUN=1
QLIB_TB_DATA_DIR=Data
```

You can still set OS-level env vars:

```powershell
setx APCA_API_KEY_ID "YOUR_KEY"
setx APCA_API_SECRET_KEY "YOUR_SECRET"
setx APCA_API_BASE_URL "https://paper-api.alpaca.markets"
setx ALPACA_PAPER "1"
setx DRY_RUN "1"
setx QLIB_TB_DATA_DIR "Data"
```

Re-open the terminal after `setx`.

## Broker Diagnostics

Run this when you see broker/trade-client wiring issues:

```powershell
python scripts/diagnose_broker.py
```

Report includes:
- `.env` discovered path
- masked key presence
- alpaca package availability
- client build success/failure

For live-mode validation:

```powershell
python scripts/diagnose_broker.py --live
```

To skip client construction and only inspect config/import readiness:

```powershell
python scripts/diagnose_broker.py --no-build
```

## Run

```powershell
conda activate qlibtradingbot
python main.py
```

Terminal menu options:
0. Exit
1. Long-term
2. Short-term
3. Intraday (EOD Flatten)
4. Scalping (5m bias + 1m trigger)
5. View Performance Analytics
6. Generate LLM post-market package
7. Intraday (3Alpha)

CLI UX behavior:
- Pressing `Ctrl+C` during a running strategy/loop stops the current run and returns to the main menu (no traceback in normal use).
- If analytics has no rows/data, the CLI prints a short message and returns to the main menu instead of exiting.

Prompted runtime config:
- NY trading window start/end
- loop mode
- max symbols
- max positions
- dollars per trade

At runtime the CLI prints the active NY session window and current NY/Sydney clock.

## Strategy behavior

- Scalping: runs 5m bias + 1m trigger, active only inside selected NY window (default 09:30-11:00).
- Intraday (EOD Flatten): closes existing positions only after 15:55 NY; does not open new positions.
- Intraday (3Alpha): can open new positions from the 3Alpha signal engine, subject to market/time/risk gates.
- Short-term: position-aware buy/sell from short-horizon model ranking.
- Long-term: position-aware buy/sell from long-horizon model ranking.
- LLM planner plugin: deterministic placeholder strategy (no live LLM call required).

## Outputs (under data dir)

- `orders.csv`
- `signals.csv`
- `positions_snapshots.csv`
- `pnl_daily.csv`
- `win_rate.csv`
- `run_log.jsonl`
- `decision_trace.jsonl`
- `position_journal.csv`
- `position_health.csv`

## Dashboards

Run:

```powershell
streamlit run qlib_tradingbot/apps/dashboard_app.py
```

Pages:
- Account Operations: cached account state cards, runtime cards, PnL line, recent orders/fills, exposure summary.
- Market Operations: macro cards (SPY/QQQ/US10Y/DXY/GOLD/SILVER/BTC), top movers/watchlist, alpha decomposition, stage funnel summary.
- Fund Flows: flow/positioning proxy tables plus risk-on/risk-off and rotation interpretation boxes.
- Position Trace: open positions, thesis-state drift, aging/review status, and latest recommended actions.

All pages are cached-data-first and show explicit empty-state guidance when files are missing.

## Troubleshooting: "Broker Client Missing" / "missing trade client"

1. Confirm `.env` exists in repo root and uses one of the supported key schemes above.
2. Run `python scripts/diagnose_broker.py`.
3. If `alpaca_available` is false, install dependencies: `pip install -r requirements.txt`.
4. If `broker_configured` is false, set keys and re-run the diagnostic.
5. Re-run the CLI after fixing config; client init now fails fast with actionable diagnostics instead of silently degrading.

## Position Traceability Workflow

1. Run strategy execution (paper/dry-run or non-dry-run).
2. Inspect `Data/decision_trace.jsonl` for fused qlib+llm+risk decisions.
3. Inspect `Data/position_journal.csv` for per-position thesis metadata.
4. Inspect `Data/position_health.csv` for latest status (`on_track`, `watch`, `risk`, `invalidated`).
5. Use Position Trace dashboard page for operational review.

## Manual LLM Workflow (Offline Pack + CSV Feedback)

1. Generate offline package:
   `python -m qlib_tradingbot.Tools.daily_llm_pack --dry-run --out Data/llm_daily_pack --strategy-type short-term`
2. Upload `llm_upload_YYYYMMDD.csv` and `llm_prompt_YYYYMMDD.txt` to your external LLM.
3. Fill the generated `feedback_template.csv` (defaults are `Neutral/50/Hold`) with returned structured feedback.
4. Ingest feedback:
   `python -m qlib_tradingbot.Tools.ingest_llm_feedback --input Data/llm_daily_pack/<DATE>/feedback_template.csv --out-dir Data/llm_feedback`
5. Run strategies; fusion reads `Data/llm_feedback/llm_bias_state.json` for governed gating.

## Tests

```powershell
pytest -q -p no:cacheprovider
```
