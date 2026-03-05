from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Iterable

import pandas as pd

from qlib_tradingbot.core import DATA_ROOT, MARKET_CACHE_ROOT


@dataclass(frozen=True)
class AccountSnapshot:
    equity: float = 0.0
    cash: float = 0.0
    buying_power: float = 0.0


class DataProvider:
    """Cached-data-first provider with optional broker adapters."""

    def __init__(self, *, data_root: Path | str = DATA_ROOT) -> None:
        self.data_root = Path(data_root)
        self.market_root = self.data_root / "market"
        self.market_root.mkdir(parents=True, exist_ok=True)

    def read_cached_csv(self, relative_path: str) -> pd.DataFrame:
        path = self.data_root / relative_path
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def read_market_series(self, symbol: str) -> pd.DataFrame:
        path = self.market_root / f"{symbol.upper()}.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def refresh_market_cache(self, symbols: Iterable[str]) -> list[Path]:
        """Offline-safe refresh path. Live adapters should override this."""
        written: list[Path] = []
        for sym in symbols:
            path = self.market_root / f"{str(sym).upper()}.csv"
            if not path.exists():
                pd.DataFrame(columns=["timestamp", "close", "volume"]).to_csv(path, index=False)
            written.append(path)
        return written


class AlpacaDataProvider(DataProvider):
    """Alpaca-backed provider with lazy imports.

    Importing this class in tests does not require alpaca-py.
    """

    def _import_clients(self):
        module = import_module("qlib_tradingbot.Brokers.alpaca_clients")
        return module

    def get_account_snapshot(self, paper: bool = True) -> AccountSnapshot:
        try:
            clients = self._import_clients()
            _dc, tc = clients.build_clients(paper=paper)
            acct = tc.get_account()
            return AccountSnapshot(
                equity=float(getattr(acct, "equity", 0.0) or 0.0),
                cash=float(getattr(acct, "cash", 0.0) or 0.0),
                buying_power=float(getattr(acct, "buying_power", 0.0) or 0.0),
            )
        except Exception:
            return AccountSnapshot()


__all__ = ["AccountSnapshot", "DataProvider", "AlpacaDataProvider", "MARKET_CACHE_ROOT"]
