from __future__ import annotations

from pathlib import Path

import pandas as pd


class ExecutionLedger:
    """Append-only order and fill ledger."""

    def __init__(self, *, root: Path | str = "Data") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.orders_path = self.root / "order_events.csv"
        self.fills_path = self.root / "trades_ledger.csv"

    @staticmethod
    def _append_csv(path: Path, frame: pd.DataFrame) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        exists = path.exists()
        frame.to_csv(path, index=False, mode="a", header=not exists)
        return path

    def append_order_events(self, frame: pd.DataFrame) -> Path:
        return self._append_csv(self.orders_path, frame)

    def append_fills(self, frame: pd.DataFrame) -> Path:
        return self._append_csv(self.fills_path, frame)


__all__ = ["ExecutionLedger"]
