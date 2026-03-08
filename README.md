# QlibTradingbot Unified Strategy Runner

Unified strategy system with Alpaca integration, Qlib-informed scoring, NY-time trading windows, and CSV-first reporting.

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

## Dashboards

Run:

```powershell
streamlit run qlib_tradingbot/apps/dashboard_app.py
```

Pages:
- Account Operations: cached account state cards, runtime cards, PnL line, recent orders/fills, exposure summary.
- Market Operations: macro cards (SPY/QQQ/US10Y/DXY/GOLD/SILVER/BTC), top movers/watchlist, alpha decomposition, stage funnel summary.
- Fund Flows: flow/positioning proxy tables plus risk-on/risk-off and rotation interpretation boxes.

All pages are cached-data-first and show explicit empty-state guidance when files are missing.

## Troubleshooting: "Broker Client Missing" / "missing trade client"

1. Confirm `.env` exists in repo root and uses one of the supported key schemes above.
2. Run `python scripts/diagnose_broker.py`.
3. If `alpaca_available` is false, install dependencies: `pip install -r requirements.txt`.
4. If `broker_configured` is false, set keys and re-run the diagnostic.
5. Re-run the CLI after fixing config; client init now fails fast with actionable diagnostics instead of silently degrading.

## Tests

```powershell
pytest -q -p no:cacheprovider
```
