from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qlib_tradingbot.Core.models import Signal
from qlib_tradingbot.Core.features_intraday import build_intraday_features
from qlib_tradingbot.Core.qlib_signal_engine import QlibSignalEngine, SignalEngineConfig
from qlib_tradingbot.Execution.engine import execute_signals
from qlib_tradingbot.LLM.feedback_handler import load_bias_state
from qlib_tradingbot.Strategies.base import StrategyBase, StrategyContext


@dataclass(frozen=True)
class AlphaWeights:
    alpha_ml: float = 0.55
    alpha_mr: float = 0.25
    alpha_mom: float = 0.20


class Intraday3AlphaStrategy(StrategyBase):
    strategy_id = "intraday_3alpha"

    def __init__(self, ctx: StrategyContext):
        self.ctx = ctx
        self._latest_snapshot = pd.DataFrame()

    def build_universe(self):
        cfg = self.ctx.config or {}
        syms = [str(s).upper() for s in cfg.get("universe_symbols", ["AAPL", "MSFT", "SPY"]) if str(s).strip()]
        return list(dict.fromkeys(syms))

    def _bars_path(self, symbol: str) -> Path:
        root = Path(self.ctx.data_dir)
        return root / "cache" / "intraday_5m" / f"{symbol.upper()}.csv"

    def _load_symbol_bars(self, symbol: str) -> pd.DataFrame:
        path = self._bars_path(symbol)
        if path.exists():
            df = pd.read_csv(path)
        else:
            # Deterministic fallback used by tests/offline mode.
            ts = pd.date_range("2026-03-02 14:30:00+00:00", periods=60, freq="5min")
            base = 100.0 + (sum(ord(c) for c in symbol) % 7)
            arr = np.linspace(base, base * 1.01, len(ts))
            df = pd.DataFrame(
                {
                    "timestamp": ts,
                    "open": arr,
                    "high": arr * 1.001,
                    "low": arr * 0.999,
                    "close": arr,
                    "volume": np.linspace(10_000, 20_000, len(ts)),
                }
            )

        if "timestamp" not in df.columns and "datetime" in df.columns:
            df = df.rename(columns={"datetime": "timestamp"})
        return df[["timestamp", "open", "high", "low", "close", "volume"]].copy()

    @staticmethod
    def _momentum_breakout_alpha(bars: pd.DataFrame) -> float:
        if bars.empty:
            return 0.0
        d = bars.copy().sort_values("timestamp")
        open_range = d.head(6)
        or_high = float(pd.to_numeric(open_range["high"], errors="coerce").max())
        or_low = float(pd.to_numeric(open_range["low"], errors="coerce").min())
        last = float(pd.to_numeric(d["close"], errors="coerce").iloc[-1])

        vol = pd.to_numeric(d["volume"], errors="coerce").fillna(0.0)
        vr = float(vol.iloc[-1] / (vol.tail(20).mean() or 1.0)) if len(vol) else 1.0

        up = (last - or_high) / or_high if or_high > 0 else 0.0
        dn = (or_low - last) / or_low if or_low > 0 else 0.0
        return float(max(-1.0, min(1.0, (up - dn) + 0.15 * (vr - 1.0))))

    @staticmethod
    def _mean_reversion_alpha(row: pd.Series) -> float:
        vwap_dist = float(row.get("vwap_dist", 0.0) or 0.0)
        bb_z = float(row.get("bb_z", 0.0) or 0.0)
        rsi = float(row.get("rsi_14", 50.0) or 50.0)
        score = (-2.0 * vwap_dist) + (-0.5 * bb_z) + (0.4 * ((50.0 - rsi) / 50.0))
        return float(max(-1.0, min(1.0, score)))

    def prepare_features(self, universe):
        rows: list[dict[str, Any]] = []
        bars_map: dict[str, pd.DataFrame] = {}
        for sym in universe or []:
            bars = self._load_symbol_bars(str(sym))
            bars_map[str(sym).upper()] = bars
            feats = build_intraday_features(bars)
            if feats.empty:
                continue
            row = feats.iloc[-1].to_dict()
            row["symbol"] = str(sym).upper()
            row["alpha_mom"] = self._momentum_breakout_alpha(bars)
            row["close_last"] = float(pd.to_numeric(bars["close"], errors="coerce").iloc[-1]) if not bars.empty else 0.0
            rows.append(row)

        frame = pd.DataFrame(rows)
        return {"feature_frame": frame, "bars_map": bars_map}

    def _bias_adjusted_thresholds(self, symbol: str, buy_th: float, sell_th: float) -> tuple[float, float]:
        cfg = self.ctx.config or {}
        state_path = cfg.get("llm_bias_state_path", Path(self.ctx.data_dir) / "llm_feedback" / "llm_bias_state.json")
        state = load_bias_state(state_path)
        rule = state.get(str(symbol).upper(), {}) if isinstance(state, dict) else {}

        bias = str(rule.get("bias", "Neutral")).lower()
        prob = float(rule.get("prob", 0.0) or 0.0)
        min_prob = float(cfg.get("llm_prob_threshold", 70.0))
        if prob < min_prob:
            return buy_th, sell_th
        if bias == "bearish":
            return buy_th * 1.15, sell_th * 0.85
        if bias == "bullish":
            return buy_th * 0.85, sell_th * 1.15
        return buy_th, sell_th

    def generate_signals(self, features):
        frame = features.get("feature_frame", pd.DataFrame())
        if frame.empty:
            self._latest_snapshot = pd.DataFrame()
            return []

        cfg = self.ctx.config or {}
        weights = AlphaWeights(
            alpha_ml=float(cfg.get("w_alpha_ml", 0.55)),
            alpha_mr=float(cfg.get("w_alpha_mr", 0.25)),
            alpha_mom=float(cfg.get("w_alpha_mom", 0.20)),
        )
        # Keep blend normalized.
        wsum = weights.alpha_ml + weights.alpha_mr + weights.alpha_mom
        if wsum <= 0:
            wsum = 1.0

        symbols = frame["symbol"].astype(str).str.upper().tolist()
        engine = QlibSignalEngine(
            data_root=Path(self.ctx.data_dir),
            config=SignalEngineConfig(model_id=str(cfg.get("qlib_model_id", "intraday_3alpha_stub_v1")), horizon="30m", strategy=self.strategy_id),
        )
        q = engine.run(
            symbols,
            strategy=self.strategy_id,
            stub=bool(cfg.get("qlib_stub_mode", True)),
            feature_frame=frame,
            timestamp=self.ctx.now_utc,
        )
        merged = frame.merge(q[["symbol", "alpha"]].rename(columns={"alpha": "alpha_ml"}), on="symbol", how="left")
        merged["alpha_ml"] = pd.to_numeric(merged["alpha_ml"], errors="coerce").fillna(0.0)
        merged["alpha_mr"] = merged.apply(self._mean_reversion_alpha, axis=1)
        merged["alpha_mom"] = pd.to_numeric(merged.get("alpha_mom", 0.0), errors="coerce").fillna(0.0)

        merged["alpha_total"] = (
            (weights.alpha_ml * merged["alpha_ml"])
            + (weights.alpha_mr * merged["alpha_mr"])
            + (weights.alpha_mom * merged["alpha_mom"])
        ) / float(wsum)

        buy_th = float(cfg.get("buy_threshold", 0.05))
        sell_th = float(cfg.get("sell_threshold", -0.05))
        allow_shorts = bool(cfg.get("allow_shorts", True))

        signals: list[Signal] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for _, r in merged.sort_values("alpha_total", ascending=False).iterrows():
            symbol = str(r["symbol"]).upper()
            bth, sth = self._bias_adjusted_thresholds(symbol, buy_th, sell_th)
            score = float(r["alpha_total"])
            side = ""
            if score >= bth:
                side = "BUY"
            elif allow_shorts and score <= sth:
                side = "SELL"
            if not side:
                continue
            signals.append(
                Signal(
                    symbol=symbol,
                    side=side,
                    strategy_id=self.strategy_id,
                    strategy_version="1.0",
                    timeframe="5Min",
                    score=score,
                    reasons="intraday_3alpha_blend",
                    signal_ts_utc=now_iso,
                    price_basis=float(r.get("close_last", 0.0) or 0.0),
                    correlation_id=self.ctx.correlation_id,
                    run_id=self.ctx.run_id,
                    features={
                        "alpha_ml": float(r["alpha_ml"]),
                        "alpha_mr": float(r["alpha_mr"]),
                        "alpha_mom": float(r["alpha_mom"]),
                        "alpha_total": float(r["alpha_total"]),
                    },
                )
            )

        self._latest_snapshot = merged.sort_values("alpha_total", ascending=False).reset_index(drop=True)
        return signals

    def execute(self, signals):
        return execute_signals(
            self.ctx.trade_client,
            list(signals or []),
            dry_run=bool((self.ctx.config or {}).get("dry_run", True)),
            dry_run_output_dir=Path(self.ctx.data_dir) / "trade_history",
            allow_shorts=bool((self.ctx.config or {}).get("allow_shorts", True)),
        )

    def post_trade_reporting(self):
        out = Path(self.ctx.data_dir) / "signals"
        out.mkdir(parents=True, exist_ok=True)
        path = out / "intraday_3alpha_signals.csv"
        self._latest_snapshot.to_csv(path, index=False)
        return {"signals_snapshot": str(path), "rows": int(len(self._latest_snapshot))}


__all__ = ["Intraday3AlphaStrategy", "AlphaWeights"]
