from __future__ import annotations

"""QLIB_TradingBot v1 configuration.

This project is designed to run in **paper trading** by default.

All secrets should be passed via environment variables (recommended for Windows + conda):
- APCA_API_KEY_ID
- APCA_API_SECRET_KEY
- APCA_API_BASE_URL  (optional; alpaca-py will route by `paper=True` anyway)

Qlib model configuration is in QLIB_* settings below.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from qlib_tradingbot.bootstrap.settings import bootstrap_environment, get_settings

bootstrap_environment()
SETTINGS = get_settings()

# ---- Runtime ----
RUN_MODE = os.getenv("RUN_MODE", "once")  # once | intraday | overnight
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"  # if True, never submits orders to Alpaca

DATA_DIR = Path(os.getenv("QLIB_TB_DATA_DIR", "Data"))
ARTIFACTS_DIR = Path(os.getenv("QLIB_TB_ARTIFACTS_DIR", "Artifacts"))

# ---- Alpaca ----
API_KEY = SETTINGS.api_key
API_SECRET = SETTINGS.api_secret
API_BASE_URL = SETTINGS.api_base_url  # optional override

PAPER = SETTINGS.paper

# Alpaca market data feed for intraday bars.
# Common values: 'iex' (free) or 'sip' (paid).
INTRADAY_FEED = os.getenv('ALPACA_INTRADAY_FEED', 'iex')

# ---- Risk / sizing ----
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))
MAX_DOLLARS_PER_TRADE = float(os.getenv("MAX_DOLLARS_PER_TRADE", "250"))
DEFAULT_TIF = os.getenv("DEFAULT_TIF", "day")

# Bracket defaults (can be overridden per signal)
DEFAULT_STOP_LOSS_PCT = float(os.getenv("DEFAULT_STOP_LOSS_PCT", "0.003"))   # 0.30%
DEFAULT_TAKE_PROFIT_PCT = float(os.getenv("DEFAULT_TAKE_PROFIT_PCT", "0.006"))  # 0.60%

# ---- Qlib ----
# Pin a stable version in requirements.txt. Docs: pip installs latest stable. citeturn1view0
QLIB_PROVIDER_URI = os.getenv("QLIB_PROVIDER_URI", str(Path.home() / ".qlib" / "qlib_data" / "us_data"))
QLIB_REGION = os.getenv("QLIB_REGION", "us")  # "us" or "cn"

# Model/training windows (for 5-min scalping model by default)
BAR_INTERVAL = os.getenv("BAR_INTERVAL", "5Min")  # Alpaca timeframe string: 1Min, 5Min, 15Min, 1Hour, 1Day
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "60"))
LABEL_HORIZON_BARS = int(os.getenv("LABEL_HORIZON_BARS", "3"))  # predict return over next N bars

# Signal thresholds
PRED_LONG_THRESHOLD = float(os.getenv("PRED_LONG_THRESHOLD", "0.0008"))   # predicted return threshold
PRED_SHORT_THRESHOLD = float(os.getenv("PRED_SHORT_THRESHOLD", "-0.0008"))

# Universe
UNIVERSE_CSV = Path(os.getenv("UNIVERSE_CSV", "Data/universe_scalp.csv"))

# ---- Convenience ----
@dataclass(frozen=True)
class StrategyId:
    id: str
    version: str

STRAT_QLOB_SCALP = StrategyId(id="QLIB_SCALP_V1", version="1.0")


# Model backend for Stage 3 scoring.
# - 'simple_lgbm' (default): uses internal LightGBM training on engineered 5m features (no pyqlib dependency)
# - 'qlib': uses pyqlib DatasetH + qlib.contrib model wrappers (requires pyqlib + extras)
MODEL_BACKEND = os.getenv('MODEL_BACKEND', 'simple_lgbm')
