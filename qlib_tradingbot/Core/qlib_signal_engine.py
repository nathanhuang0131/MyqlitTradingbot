from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from qlib_tradingbot.core import DATA_ROOT

SIGNAL_COLUMNS = ["symbol", "timestamp", "alpha", "direction", "confidence", "horizon", "model_id"]


@dataclass(frozen=True)
class SignalEngineConfig:
    model_id: str = "qlib_stub_v1"
    horizon: str = "1D"


class QlibSignalEngine:
    """Single source of alpha ranking for strategies.

    This implementation is offline-safe and deterministic by default.
    """

    def __init__(self, *, data_root: Path | str = DATA_ROOT, config: SignalEngineConfig = SignalEngineConfig()) -> None:
        self.data_root = Path(data_root)
        self.config = config

    @staticmethod
    def _deterministic_alpha(symbol: str) -> float:
        seed = sum((i + 1) * ord(ch) for i, ch in enumerate(symbol.upper()))
        return ((seed % 2001) - 1000) / 1000.0

    def _from_cached_predictions(self) -> pd.DataFrame:
        path = self.data_root / "qlib_preds_latest.csv"
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(path)
        except Exception:
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()
        symbol_col = "symbol" if "symbol" in df.columns else ("instrument" if "instrument" in df.columns else None)
        alpha_col = "pred" if "pred" in df.columns else ("alpha" if "alpha" in df.columns else None)
        ts_col = "datetime" if "datetime" in df.columns else ("timestamp" if "timestamp" in df.columns else None)
        if symbol_col is None or alpha_col is None:
            return pd.DataFrame()

        out = pd.DataFrame()
        out["symbol"] = df[symbol_col].astype(str).str.upper()
        out["alpha"] = pd.to_numeric(df[alpha_col], errors="coerce").fillna(0.0)
        out["timestamp"] = (
            pd.to_datetime(df[ts_col], utc=True, errors="coerce") if ts_col is not None else pd.Timestamp.now(tz="UTC")
        )
        out["timestamp"] = out["timestamp"].fillna(pd.Timestamp.now(tz="UTC"))
        return out

    def run(
        self,
        symbols: Iterable[str],
        *,
        timestamp: datetime | None = None,
        stub: bool = False,
    ) -> pd.DataFrame:
        syms = [str(s).upper().strip() for s in symbols if str(s).strip()]
        if not syms:
            return pd.DataFrame(columns=SIGNAL_COLUMNS)

        now = timestamp or datetime.now(timezone.utc)
        if timestamp is not None and timestamp.tzinfo is None:
            now = timestamp.replace(tzinfo=timezone.utc)

        cached = self._from_cached_predictions() if not stub else pd.DataFrame()
        rows: list[dict] = []
        for sym in syms:
            if not cached.empty and sym in set(cached["symbol"]):
                rec = cached[cached["symbol"] == sym].iloc[-1]
                alpha = float(rec["alpha"])
                ts = pd.Timestamp(rec["timestamp"]).to_pydatetime()
            else:
                alpha = float(self._deterministic_alpha(sym))
                ts = now
            rows.append(
                {
                    "symbol": sym,
                    "timestamp": pd.Timestamp(ts).tz_convert("UTC").isoformat() if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts).tz_localize("UTC").isoformat(),
                    "alpha": alpha,
                    "direction": "BUY" if alpha >= 0 else "SELL",
                    "confidence": min(1.0, max(0.0, abs(alpha))),
                    "horizon": self.config.horizon,
                    "model_id": self.config.model_id,
                }
            )

        frame = pd.DataFrame(rows, columns=SIGNAL_COLUMNS)
        return frame.sort_values("alpha", ascending=False).reset_index(drop=True)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Run Qlib signal engine")
    parser.add_argument("--stub", action="store_true", help="Run deterministic stub mode")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--symbols", default="AAPL,MSFT,SPY", help="Comma separated symbols")
    parser.add_argument("--model-id", default="qlib_stub_v1", help="Model ID")
    parser.add_argument("--horizon", default="1D", help="Signal horizon")
    args = parser.parse_args()

    engine = QlibSignalEngine(config=SignalEngineConfig(model_id=args.model_id, horizon=args.horizon))
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    frame = engine.run(symbols, stub=bool(args.stub))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
