from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PACKAGE_ROOT / "Data"
MARKET_CACHE_ROOT = DATA_ROOT / "market"

__all__ = ["PACKAGE_ROOT", "DATA_ROOT", "MARKET_CACHE_ROOT"]
