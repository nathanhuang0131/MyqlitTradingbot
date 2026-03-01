# QlibTradingbot Unified Strategy Runner

Unified strategy system with Alpaca integration, Qlib-informed scoring, NY-time trading windows, and CSV-first reporting.

## Windows (Conda) setup

```powershell
conda create -n qlibtradingbot python=3.11 -y
conda activate qlibtradingbot
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Required environment variables

```powershell
setx APCA_API_KEY_ID "YOUR_KEY"
setx APCA_API_SECRET_KEY "YOUR_SECRET"
setx APCA_API_BASE_URL "https://paper-api.alpaca.markets"
setx ALPACA_PAPER "1"
setx DRY_RUN "1"
setx QLIB_TB_DATA_DIR "Data"
```

Re-open the terminal after `setx`.

## Run

```powershell
conda activate qlibtradingbot
python main.py
```

Terminal menu options:
1. Long-term
2. Short-term
3. Intraday
4. Scalping (5m bias + 1m trigger)

Prompted runtime config:
- NY trading window start/end
- loop mode
- max symbols
- max positions
- dollars per trade

At runtime the CLI prints the active NY session window and current NY/Sydney clock.

## Strategy behavior

- Scalping: runs 5m bias + 1m trigger, active only inside selected NY window (default 09:30-11:00).
- Intraday: intraday behavior with optional EOD flattening (`force_eod_flat`).
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

## Tests

```powershell
pytest -q -p no:cacheprovider
```
