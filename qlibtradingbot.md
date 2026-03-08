# QLIB_TradingBot v2 — Qlib + Alpaca (Paper) — 3‑Stage Scalping Pipeline

This repo is the **v2** iteration of your QLIB trading bot. It combines:

- **Alpaca** for market data + paper trading
- **Microsoft Qlib** as the **core ML scoring model**
- A **3-stage** DT-2 scalping pipeline adapted from your working MyTradingBot Strategy 3 code:
  - **Stage 1**: discover **all active tradable US equities** from Alpaca assets API
  - **Stage 2**: prescreen using **daily bars** (liquidity + volatility + spread proxy), with **batching + caching**
  - **Stage 3**: build features from **5-minute bars** and run a **Qlib LightGBM model** to score and produce signals
- A monitoring loop that keeps scoring the **final daily universe** every N minutes and (optionally) places orders.

Outputs are CSV-first so you can backtest and review easily in Excel / PowerBI.

---

## What’s new in v2

### 1) Proper “discover from all symbols” flow
Stage 1 pulls Alpaca **active tradable** assets and reduces to candidate symbols (metadata-only).

### 2) Batched + cached market data
We ported the working batching/caching code from your MyTradingBot:
- per-symbol CSV cache under `Data/cache/`
- batching across symbols for Alpaca bar requests
- pacing + retries

### 3) Automatic final “trade universe” file
The pipeline writes:

- `Data/universe_stage1.csv`
- `Data/universe_stage2.csv`
- `Data/universe_trade_today.csv`  ✅ **this is what the monitor loop uses**
- `Data/qlib_preds_latest.csv`
- `Data/trade_signals_latest.csv`

---

## Limitations / Notes

1) **Scanning “all symbols” does NOT mean fetching 5-minute bars for all symbols.**  
   Stage 1 is metadata-only; Stage 2 uses daily bars; Stage 3 uses 5m bars only after filtering.

2) Qlib model here is a **lightweight baseline**:
   - feature set is computed from Alpaca OHLCV bars (see `qlib_tradingbot/Qlib/dataset.py`)
   - model is LightGBM via Qlib contrib wrapper
   - you can later swap in more advanced Qlib pipelines (handlers, trainers, rolling retrain, etc.)

3) Options like CatBoost / XGBoost / PyTorch are optional. If you don’t install them, Qlib will warn and skip those models.

---

## Python / Qlib versions (recommended)

- Python: **3.11**
- Install Qlib via pip in conda (stable release), **avoid dev branches**.

---

## Installation (Conda on Windows)

From Anaconda Prompt:

```bat
conda create -n qlibtradingbot python=3.11 -y
conda activate qlibtradingbot
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If you see Qlib warnings about optional models (CatBoost/XGBoost/PyTorch), that’s normal unless you plan to use those models.

---

## Alpaca keys (copying from another environment)

**Best practice:** set them at **User or System** environment variable level, not “conda env vars”.

Set (paper):
- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `APCA_API_BASE_URL` = `https://paper-api.alpaca.markets`

### Windows PowerShell (User-level)
```powershell
setx APCA_API_KEY_ID "YOUR_KEY"
setx APCA_API_SECRET_KEY "YOUR_SECRET"
setx APCA_API_BASE_URL "https://paper-api.alpaca.markets"
```

Close and reopen your terminal after `setx`.

### Verify
```bat
python -c "import os; print(os.getenv('APCA_API_KEY_ID')); print(os.getenv('APCA_API_BASE_URL'))"
```

---

## Running the bot (interactive)

```bat
python main.py
```

It will prompt you for Stage 2/3 parameters and then:

1) run Stage 1→2→3 pipeline  
2) write universes + predictions  
3) ask if you want to start the monitoring loop

---

## Parameter tuning (what to change first)

Stage 2 (daily prescreen) is the main “size control”:

- `keep_top_n`  
  - start with **800** if your connection is stable  
  - if you hit throttling, lower to **300–500**

- `min_price`  
  - scalping: **15** is a good default

- `min_avg_volume_20d`  
  - scalping: start at **2,000,000**, adjust up for tighter spreads

- `min_atr_pct_14d`  
  - scalping needs movement: start at **1%**

- `max_spread_proxy_20d`  
  - start at **2%** (0.02), tighten toward **1%** if you want cleaner fills

Stage 3 (Qlib scoring):

- `top_n_signals`: start at **30**
- If no signals meet thresholds, the bot will still create a **monitor list** (`monitor_top_n_by_pred` default 60).

---

## Overnight workflow (recommended)

**Night (or premarket):**
- Run pipeline once to build today’s universe:  
  `python main.py` → run Stage 1→2→3 and stop (don’t monitor yet)

**Market session:**
- Start monitoring loop to re-score every 5 minutes:
  - interval: 5 minutes
  - duration: 4–6 hours (or until 11:00 ET)

This is more stable than trying to pull huge data volumes during the open.

---

## Testing

```bat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

---

## Repo layout

- `qlib_tradingbot/Strategies/scalp_pipeline_qlib.py` — **v2 3-stage pipeline**
- `qlib_tradingbot/Data/batch_bars.py` + `qlib_tradingbot/Data/cache.py` — batching + caching
- `qlib_tradingbot/Qlib/` — dataset + model wrappers
- `qlib_tradingbot/Execution/` — orders + execution engine (bracket/simple)
- `Data/` — generated CSV outputs

---

## Next upgrades (recommended)

1) Add a proper **rolling retrain** schedule:
   - nightly retrain on last N days of 5m bars
   - save artifacts under `Artifacts/models/...` and load during the day

2) Add performance reporting:
   - daily P&L by strategy + symbol
   - win rate, expectancy, drawdown
   - link fills from Alpaca activities into `fills.csv`

3) Add a stricter **rate-limit governor**:
   - adaptive pacing based on Alpaca headers / error patterns
