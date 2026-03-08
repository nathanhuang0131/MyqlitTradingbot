from __future__ import annotations

"""
qlib_tradingbot/Strategies/scalp_pipeline_qlib.py

3-stage scalping pipeline (Alpaca -> prescreen -> Qlib model -> trade universe)

This is adapted from your MyTradingBot Strategy 3 (DT-2) 3-stage pipeline:
- Stage 1: Discover from Alpaca active tradable US equities (assets metadata only)
- Stage 2: Liquidity/volatility prescreen using DAILY bars (batched + cached)
- Stage 3: Qlib LightGBM model scoring using 5-minute bars (batched + cached)

Outputs (CSV):
- Data/universe_stage1.csv
- Data/universe_stage2.csv
- Data/universe_trade_today.csv
- Data/qlib_preds_latest.csv
- Data/trade_signals_latest.csv

Design goals:
- Avoid rate-limit blocks by batching requests and caching results to Data/cache
- Allow user to tune parameters (via config.py and/or env vars and/or CLI args)
- Keep deterministic unit tests (fake clients + synthetic bars)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from qlib_tradingbot.Data.batch_bars import BatchFetchConfig as BatchBarsConfig, fetch_daily_bars_batch as get_daily_bars_batched, fetch_5m_bars_batch as get_intraday_bars_batched
from qlib_tradingbot.Data.logs import ensure_data_dirs, write_csv_atomic
from qlib_tradingbot.Qlib.dataset import build_qlib_dataset_from_bars
from qlib_tradingbot.Qlib.model import train_lightgbm, predict
from qlib_tradingbot.Strategies.scalping_qlib import signals_from_predictions
from qlib_tradingbot.config import (
    PRED_LONG_THRESHOLD,
    PRED_SHORT_THRESHOLD,
)

# ----------------------------
# Config
# ----------------------------

@dataclass(frozen=True)
class Stage1Config:
    asset_class: str = "us_equity"
    tradable_only: bool = True
    allow_otc: bool = False
    allow_crypto: bool = False
    include_etfs: bool = True  # Alpaca assets include ETFs as us_equity; keep them


@dataclass(frozen=True)
class Stage2Config:
    # fast liquidity / volatility filters (DAILY bars)
    min_price: float = 15.0
    min_avg_volume_20d: float = 2_000_000.0
    min_atr_pct_14d: float = 0.01          # 1%
    max_spread_proxy_20d: float = 0.02     # 2% proxy via (high-low)/close
    keep_top_n: int = 800                  # after ranking, keep top N
    corr_gate_etf: Optional[str] = None    # optional: require corr vs ETF >= threshold
    corr_min: float = 0.30                # if corr_gate_etf is set


@dataclass(frozen=True)
class Stage3Config:
    top_n_signals: int = 30
    allow_shorts: bool = False
    # If True, stage 3 will also output a smaller "monitor list" even if no signals hit thresholds.
    monitor_top_n_by_pred: int = 60
    # If Stage 2 filters are too strict, we still want enough symbols for ML training and a stable
    # distribution of predictions. This is a *training/monitoring* minimum, not an execution minimum.
    min_stage3_symbols: int = 60
    # Always try to include a few broad ETFs for stability/representativeness (if present in Stage 1/2 universe).
    include_etf_anchors: bool = True


@dataclass(frozen=True)
class PipelineConfig:
    stage1: Stage1Config = Stage1Config()
    stage2: Stage2Config = Stage2Config()
    stage3: Stage3Config = Stage3Config()
    batch: BatchBarsConfig = BatchBarsConfig()
    # history windows
    lookback_days_daily: int = 60
    lookback_days_5m: int = 14


# ----------------------------
# Stage 1: discovery from Alpaca assets
# ----------------------------

def fetch_alpaca_active_assets(trade_client) -> List[Any]:
    """
    Return Alpaca assets (best-effort across alpaca-py versions).
    We only need a few fields: symbol, tradable, asset_class, exchange.
    """
    # alpaca-py (newer)
    try:
        from alpaca.trading.requests import GetAssetsRequest
        from alpaca.trading.enums import AssetStatus

        req = GetAssetsRequest(status=AssetStatus.ACTIVE)
        assets = trade_client.get_all_assets(req)
        return list(assets or [])
    except Exception:
        pass

    # older shapes
    try:
        assets = trade_client.get_all_assets(status="active")
        return list(assets or [])
    except Exception:
        pass

    try:
        assets = trade_client.get_assets(status="active")
        return list(assets or [])
    except Exception:
        return []



def _enum_to_value(x: Any) -> Any:
    """Return Enum.value when available, else the object itself."""
    try:
        return x.value  # type: ignore[attr-defined]
    except Exception:
        return x


def _normalize_asset_class(x: Any) -> str:
    v = _enum_to_value(x)
    s = str(v or "").strip().lower()
    # Handle alpaca enums stringified like "AssetClass.US_EQUITY"
    if "." in s:
        s = s.split(".")[-1]
    return s


def _normalize_exchange(x: Any) -> str:
    v = _enum_to_value(x)
    s = str(v or "").strip().upper()
    if "." in s:
        s = s.split(".")[-1]
    return s

def stage1_reduce_universe(assets: Sequence[Any], cfg: Stage1Config) -> List[str]:
    out: List[str] = []
    for a in assets:
        sym = str(getattr(a, "symbol", "") or "").upper().strip()
        if not sym:
            continue

        asset_class = _normalize_asset_class(getattr(a, "asset_class", ""))
        if cfg.asset_class and asset_class and asset_class != cfg.asset_class.lower():
            # If Alpaca provides asset_class, enforce it.
            continue

        if cfg.tradable_only:
            if bool(getattr(a, "tradable", True)) is False:
                continue

        exch = _normalize_exchange(getattr(a, "exchange", ""))
        if not cfg.allow_otc and exch in {"OTC", "OTCQB", "OTCQX"}:
            continue

        out.append(sym)

    # de-dupe while preserving order
    seen = set()
    uniq = []
    for s in out:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq


# ----------------------------
# Stage 2: liquidity/volatility prescreen (daily bars)
# ----------------------------

def _calc_atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    """
    df: daily bars for a single symbol, sorted by datetime, columns: high, low, close
    Returns latest ATR% value (atr/close).
    """
    if df is None or df.empty or len(df) < (period + 2):
        return float("nan")
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    last_atr = float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else float("nan")
    last_close = float(close.iloc[-1]) if pd.notna(close.iloc[-1]) and float(close.iloc[-1]) != 0 else float("nan")
    return (last_atr / last_close) if last_close and pd.notna(last_close) else float("nan")


def _spread_proxy(df: pd.DataFrame, window: int = 20) -> float:
    """
    Proxy: median((high-low)/close) over the window.
    """
    if df is None or df.empty or len(df) < window:
        return float("nan")
    x = ((df["high"].astype(float) - df["low"].astype(float)).abs() / df["close"].astype(float).replace(0, pd.NA)).tail(window)
    return float(x.median())


def apply_filters_with_breakdown(
    symbols: Sequence[str],
    filters: Sequence[tuple[str, Any]],
) -> tuple[list[str], dict[str, dict[str, int]]]:
    current = [str(s).upper() for s in symbols if str(s).strip()]
    breakdown: dict[str, dict[str, int]] = {}
    for name, predicate in filters:
        in_count = len(current)
        out: list[str] = []
        for sym in current:
            keep = False
            try:
                keep = bool(predicate(sym))
            except Exception:
                keep = False
            if keep:
                out.append(sym)
        out_count = len(out)
        breakdown[str(name)] = {
            "in_count": int(in_count),
            "out_count": int(out_count),
            "removed": int(in_count - out_count),
        }
        current = out
    return current, breakdown


def stage2_liquidity_filter(
    data_client,
    *,
    symbols: Sequence[str],
    cfg: Stage2Config,
    batch_cfg: BatchBarsConfig,
    lookback_days: int,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, pd.DataFrame]]:
    """
    Returns:
      passed_df: rows for symbols that passed filters + ranking columns
      funnel_df: per-symbol pass/fail with RejectReason
      bars_map: dict symbol -> daily bars df
    """
    ensure_data_dirs()
    symbols = [str(s).upper() for s in symbols if str(s).strip()]
    if not symbols:
        return pd.DataFrame(), pd.DataFrame(), {}

    bars_map = get_daily_bars_batched(
        data_client,
        symbols=symbols,
        lookback_days=lookback_days,
        cfg=batch_cfg,
    )

    metrics_by_symbol: dict[str, dict[str, float]] = {}
    funnel = []

    for sym in symbols:
        df = bars_map.get(sym)
        if df is None or df.empty:
            funnel.append({"Symbol": sym, "Pass": False, "RejectReason": "no_daily_bars"})
            continue

        # Alpaca daily bars commonly come back with a "timestamp" column (or a datetime index).
        # Older iterations of this project used "datetime". Normalize here so Stage 2 never
        # fails on missing columns.
        if "datetime" in df.columns:
            sort_col = "datetime"
        elif "timestamp" in df.columns:
            sort_col = "timestamp"
        else:
            # If the index is datetime-like, use it.
            sort_col = None
            try:
                if pd.api.types.is_datetime64_any_dtype(df.index):
                    df = df.reset_index().rename(columns={"index": "timestamp"})
                    sort_col = "timestamp"
            except Exception:
                sort_col = None

        if sort_col is not None and sort_col in df.columns:
            df = df.sort_values(sort_col)
        else:
            df = df.reset_index(drop=True)
        last_close = float(df["close"].iloc[-1])
        avg_vol20 = float(df["volume"].astype(float).tail(20).mean()) if len(df) >= 20 else float(df["volume"].astype(float).mean())
        atr_pct = _calc_atr_pct(df, period=14)
        sp = _spread_proxy(df, window=20)
        dollar_vol = float(last_close * avg_vol20)
        metrics_by_symbol[sym] = {
            "LastClose": float(last_close),
            "AvgVol20": float(avg_vol20),
            "DollarVol20": float(dollar_vol),
            "ATR_Pct14": float(atr_pct) if pd.notna(atr_pct) else float("nan"),
            "SpreadProxy20": float(sp) if pd.notna(sp) else float("nan"),
        }

        # Determine pass/fail + first reject reason, but *always* record diagnostics so we can
        # select a representative fallback universe for Stage 3.
        reject = ""
        if last_close < float(cfg.min_price):
            reject = "min_price"
        elif avg_vol20 < float(cfg.min_avg_volume_20d):
            reject = "min_avg_volume_20d"
        elif (not pd.notna(atr_pct)) or atr_pct < float(cfg.min_atr_pct_14d):
            reject = "min_atr_pct_14d"
        elif (not pd.notna(sp)) or sp > float(cfg.max_spread_proxy_20d):
            reject = "max_spread_proxy_20d"

        passed = reject == ""
        funnel.append(
            {
                "Symbol": sym,
                "Pass": bool(passed),
                "RejectReason": reject,
                **metrics_by_symbol[sym],
            }
        )

    filters = [
        ("has_daily_bars", lambda s: s in metrics_by_symbol),
        ("min_price", lambda s: float(metrics_by_symbol[s]["LastClose"]) >= float(cfg.min_price)),
        ("min_avg_volume_20d", lambda s: float(metrics_by_symbol[s]["AvgVol20"]) >= float(cfg.min_avg_volume_20d)),
        ("min_atr_pct_14d", lambda s: pd.notna(metrics_by_symbol[s]["ATR_Pct14"]) and float(metrics_by_symbol[s]["ATR_Pct14"]) >= float(cfg.min_atr_pct_14d)),
        ("max_spread_proxy_20d", lambda s: pd.notna(metrics_by_symbol[s]["SpreadProxy20"]) and float(metrics_by_symbol[s]["SpreadProxy20"]) <= float(cfg.max_spread_proxy_20d)),
    ]
    passed_symbols, breakdown = apply_filters_with_breakdown(symbols, filters)
    passed_rows = [{"Symbol": s, **metrics_by_symbol[s]} for s in passed_symbols if s in metrics_by_symbol]
    passed_df = pd.DataFrame(passed_rows)
    funnel_df = pd.DataFrame(funnel)
    funnel_df.attrs["filters_breakdown"] = breakdown

    if not passed_df.empty:
        # rank: prefer high dollar volume and sufficient ATR%
        passed_df = passed_df.sort_values(["DollarVol20", "ATR_Pct14"], ascending=[False, False])
        if int(cfg.keep_top_n) > 0:
            passed_df = passed_df.head(int(cfg.keep_top_n)).reset_index(drop=True)

    return passed_df, funnel_df, bars_map


# ----------------------------
# Stage 3: Qlib model scoring (5-minute bars)
# ----------------------------


def stage3_qlib_score(
    data_client,
    *,
    symbols: Sequence[str],
    batch_cfg: BatchBarsConfig,
    lookback_days_5m: int,
    cfg: Stage3Config,
) -> Tuple[pd.Series, pd.DataFrame]:
    """
    Stage 3 scoring on 5m bars.

    Backends:
      - config.MODEL_BACKEND == "simple_lgbm": train LightGBM directly on engineered 5m features (no pyqlib)
      - config.MODEL_BACKEND == "qlib": build a Qlib DatasetH and use qlib.contrib model wrappers (requires pyqlib)

    Returns:
      preds: pd.Series indexed by (datetime, symbol)
      bars_df: concatenated raw 5m bars used
    """
    symbols = [str(s).upper() for s in symbols if str(s).strip()]
    if not symbols:
        return pd.Series(dtype=float), pd.DataFrame()

    bars_map = get_intraday_bars_batched(
        data_client,
        symbols=symbols,
        lookback_days=lookback_days_5m,
        cfg=batch_cfg,
    )

    frames = []
    for sym, df in (bars_map or {}).items():
        if df is None or df.empty:
            continue
        dfx = df.copy()
        dfx["symbol"] = str(sym).upper()
        frames.append(dfx)

    bars_df = pd.concat(frames, axis=0, ignore_index=True) if frames else pd.DataFrame()
    if bars_df.empty:
        return pd.Series(dtype=float), pd.DataFrame()

    # ensure expected columns
    if "datetime" not in bars_df.columns:
        return pd.Series(dtype=float), bars_df

    # Need enough history to train something non-trivial
    all_times = pd.to_datetime(bars_df["datetime"], utc=True).sort_values().unique()
    if len(all_times) < 200:
        return pd.Series(dtype=float), bars_df

    # Choose backend
    from qlib_tradingbot import config as app_cfg

    backend = getattr(app_cfg, "MODEL_BACKEND", "simple_lgbm").lower().strip()
    if backend != "qlib":
        # simple LightGBM backend
        from qlib_tradingbot.ML.lgbm_scalp import (
            build_features_and_label,
            train_simple_lgbm,
            predict_simple_lgbm,
        )

        

        bundle = build_features_and_label(
            bars_df,
            horizon_bars=getattr(app_cfg, "LABEL_HORIZON_BARS", 3),
        )

        # Write dataset diagnostics each run (feature NaN %, label distribution, samples per symbol)
        try:
            from qlib_tradingbot.ML.lgbm_scalp import write_training_diagnostics
            from qlib_tradingbot.config import ARTIFACTS_DIR

            write_training_diagnostics(
                bundle,
                out_dir=ARTIFACTS_DIR / "training_diagnostics",
                prefix="stage3_simple_lgbm",
            )
        except Exception:
            pass

        model = train_simple_lgbm(bundle)
        preds = predict_simple_lgbm(model, bundle)
        # Return only the latest timestamp per symbol for "trade now" decisions
        latest_ts = preds.index.get_level_values(0).max()
        latest = preds.loc[latest_ts]
        latest.index = pd.MultiIndex.from_product([[latest_ts], latest.index], names=["datetime","symbol"])
        latest.name = "pred"

        # Diagnostics (helps detect degenerate training where preds collapse to ~0)
        try:
            m = float(latest.mean())
            s = float(latest.std())
            mx = float(latest.max())
            mn = float(latest.min())
            print(f"[Stage3] pred stats: n={len(latest)} mean={m:.6g} std={s:.6g} min={mn:.6g} max={mx:.6g}")
        except Exception:
            pass
        return latest, bars_df

    # Qlib backend (optional)
    try:
        bundle = build_qlib_dataset_from_bars(
            bars_df,
            train_start=str(pd.Timestamp(all_times[0]).date()),
            train_end=str(pd.Timestamp(all_times[int(len(all_times)*0.70)]).date()),
            valid_end=str(pd.Timestamp(all_times[int(len(all_times)*0.85)]).date()),
            test_end=str(pd.Timestamp(all_times[-1]).date()),
        )
        model = train_lightgbm(bundle)
        preds = predict(model, bundle, segment="test")

        try:
            # Qlib preds are multi-indexed; show stats on the latest timestamp
            idx = preds.index
            latest_dt = idx.get_level_values(0).max()
            latest = preds.xs(latest_dt, level=0).dropna()
            if len(latest):
                m = float(latest.mean())
                s = float(latest.std())
                mx = float(latest.max())
                mn = float(latest.min())
                print(f"[Stage3] pred stats: n={len(latest)} mean={m:.6g} std={s:.6g} min={mn:.6g} max={mx:.6g}")
        except Exception:
            pass
        return preds, bars_df
    except Exception:
        # If Qlib isn't available, don't crash the pipeline
        return pd.Series(dtype=float), bars_df


def _choose_stage3_symbols(
    *,
    passed_df: pd.DataFrame,
    funnel_df: pd.DataFrame,
    cfg2: Stage2Config,
    cfg3: Stage3Config,
) -> List[str]:
    """Pick a Stage-3 symbol list that is both tradable and large enough for ML.

    We prefer the strict Stage-2 pass list, but if it is too small we fall back to the most liquid
    candidates that *have daily data*.

    "Representative" here means:
      - Liquid names (high dollar volume)
      - Some volatility (ATR%)
      - Optionally a handful of broad ETFs to stabilize the distribution
    """

    finalists: List[str] = []
    if passed_df is not None and not passed_df.empty and "Symbol" in passed_df.columns:
        finalists = passed_df["Symbol"].astype(str).str.upper().tolist()

    min_needed = int(getattr(cfg3, "min_stage3_symbols", 0) or 0)
    if min_needed <= 0:
        return list(dict.fromkeys(finalists))

    # Add anchors (if present in the stage-2 funnel)
    anchors: List[str] = []
    if bool(getattr(cfg3, "include_etf_anchors", True)) and funnel_df is not None and not funnel_df.empty:
        anchor_syms = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE"]
        present = set(funnel_df.get("Symbol", pd.Series(dtype=str)).astype(str).str.upper().tolist())
        anchors = [a for a in anchor_syms if a in present]

    finalists = list(dict.fromkeys([*anchors, *finalists]))
    if len(finalists) >= min_needed:
        return finalists

    if funnel_df is None or funnel_df.empty:
        return finalists

    # Candidates: must have metrics computed (i.e., had daily bars)
    cand = funnel_df.copy()
    if "DollarVol20" not in cand.columns:
        return finalists

    # Relaxed guards to avoid pulling illiquid junk
    min_price = float(cfg2.min_price)
    min_vol = float(cfg2.min_avg_volume_20d)
    max_sp = float(cfg2.max_spread_proxy_20d)

    cand["Symbol"] = cand["Symbol"].astype(str).str.upper()
    cand = cand.dropna(subset=["DollarVol20"])
    cand = cand[(cand["LastClose"].astype(float) >= min_price)]
    cand = cand[(cand["AvgVol20"].astype(float) >= max(1.0, 0.5 * min_vol))]
    if "SpreadProxy20" in cand.columns:
        cand = cand[(cand["SpreadProxy20"].astype(float) <= 1.5 * max_sp) | (~pd.notna(cand["SpreadProxy20"]))]

    cand = cand.sort_values(["DollarVol20", "ATR_Pct14"], ascending=[False, False])
    pool = cand["Symbol"].tolist()

    for s in pool:
        if s not in finalists:
            finalists.append(s)
        if len(finalists) >= min_needed:
            break

    return finalists


def run_3stage_qlib_scalp_pipeline(
    *,
    data_client,
    trade_client,
    run_id: str,
    correlation_id: str,
    cfg: PipelineConfig = PipelineConfig(),
    output_dir: str = "Data",
    stage_monitor: Any | None = None,
) -> Dict[str, Any]:
    """
    Run stages, write outputs, and return a debug summary dict.
    """
    ensure_data_dirs()
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    debug: Dict[str, Any] = {"run_id": run_id, "correlation_id": correlation_id}
    t0 = datetime.now(timezone.utc)

    def _monitor_log(stage: str, status: str, message: str, metrics: dict[str, Any] | None = None, sample_symbols: list[str] | None = None, error: str | None = None) -> None:
        if stage_monitor is None:
            return
        try:
            stage_monitor.log(
                stage=stage,
                status=status,
                message=message,
                metrics=metrics or {},
                sample_symbols=sample_symbols or [],
                error=error,
            )
        except Exception:
            return

    # Stage 1
    stage1_t0 = perf_counter()
    stage1_error = None
    try:
        assets = fetch_alpaca_active_assets(trade_client) if trade_client is not None else []
    except Exception as exc:  # pragma: no cover - defensive
        assets = []
        stage1_error = str(exc)
    stage1_ms = int((perf_counter() - stage1_t0) * 1000)
    sample_assets = [str(getattr(a, "symbol", "")).upper() for a in assets[:20] if str(getattr(a, "symbol", "")).strip()]
    _monitor_log(
        "stage1_alpaca_fetch",
        "ok" if stage1_error is None else "fail",
        "alpaca active assets fetch",
        metrics={
            "fetch_ok": stage1_error is None,
            "symbols_returned_total": int(len(assets)),
            "duration_ms": stage1_ms,
        },
        sample_symbols=sample_assets,
        error=stage1_error,
    )
    stage1_syms = stage1_reduce_universe(assets, cfg.stage1)
    debug["stage1_count"] = len(stage1_syms)
    _monitor_log(
        "stage1_universe",
        "ok",
        "stage1 universe built",
        metrics={
            "stage1_universe_size": int(len(stage1_syms)),
            "stage1_filters": {
                "tradable_only": bool(cfg.stage1.tradable_only),
                "allow_otc": bool(cfg.stage1.allow_otc),
                "asset_class": str(cfg.stage1.asset_class),
            },
        },
        sample_symbols=stage1_syms[:20],
    )
    write_csv_atomic(outdir / "universe_stage1.csv", pd.DataFrame({"Symbol": stage1_syms}))

    # Stage 2
    passed_df, funnel_df, daily_map = stage2_liquidity_filter(
        data_client,
        symbols=stage1_syms,
        cfg=cfg.stage2,
        batch_cfg=cfg.batch,
        lookback_days=int(cfg.lookback_days_daily),
    )
    debug["stage2_passed"] = int(len(passed_df))
    stage2_breakdown = {}
    try:
        stage2_breakdown = dict(funnel_df.attrs.get("filters_breakdown", {}) or {})
    except Exception:
        stage2_breakdown = {}
    _monitor_log(
        "stage2_filters",
        "ok",
        "stage2 filters applied",
        metrics={
            "stage2_input_size": int(len(stage1_syms)),
            "stage2_output_size": int(len(passed_df)),
            "filters_breakdown": stage2_breakdown,
        },
        sample_symbols=(passed_df["Symbol"].astype(str).str.upper().tolist()[:20] if not passed_df.empty and "Symbol" in passed_df.columns else []),
    )
    write_csv_atomic(outdir / "universe_stage2.csv", passed_df)
    write_csv_atomic(outdir / "universe_stage2_funnel.csv", funnel_df)

    finalists = passed_df["Symbol"].astype(str).tolist() if not passed_df.empty else []

    # Ensure we have enough symbols for ML training + a stable prediction distribution.
    finalists = _choose_stage3_symbols(
        passed_df=passed_df,
        funnel_df=funnel_df,
        cfg2=cfg.stage2,
        cfg3=cfg.stage3,
    )
    debug["stage3_symbols"] = int(len(finalists))
    _monitor_log(
        "stage3_monitor_universe",
        "ok",
        "stage3 monitor universe selected",
        metrics={"final_universe_size": int(len(finalists))},
        sample_symbols=finalists[:20],
    )

    # Stage 3
    stage3_t0 = perf_counter()
    preds, bars_df = stage3_qlib_score(
        data_client,
        symbols=finalists,
        batch_cfg=cfg.batch,
        lookback_days_5m=int(cfg.lookback_days_5m),
        cfg=cfg.stage3,
    )
    stage3_ms = int((perf_counter() - stage3_t0) * 1000)
    bars_received_symbols = 0
    if bars_df is not None and not bars_df.empty and "symbol" in bars_df.columns:
        bars_received_symbols = int(bars_df["symbol"].astype(str).str.upper().nunique())
    _monitor_log(
        "stage3_data_fetch",
        "ok",
        "stage3 bars fetched",
        metrics={
            "bars_requested_symbols": int(len(finalists)),
            "bars_received_symbols": int(bars_received_symbols),
            "bars_missing_symbols_count": int(max(0, len(finalists) - bars_received_symbols)),
            "duration_ms": int(stage3_ms),
        },
    )
    debug["preds_len"] = int(len(preds)) if preds is not None else 0

    # Signals + monitoring list
    price_basis = {row["Symbol"]: float(row["LastClose"]) for _, row in passed_df.iterrows()} if not passed_df.empty else {}
    selection = signals_from_predictions(
        preds,
        top_n=int(cfg.stage3.top_n_signals),
        allow_shorts=bool(cfg.stage3.allow_shorts),
        price_basis_by_symbol=price_basis,
    )
    signals_buy = sum(1 for s in (selection.signals or []) if str(getattr(s, "side", "")).upper() == "BUY")
    signals_sell = sum(1 for s in (selection.signals or []) if str(getattr(s, "side", "")).upper() == "SELL")
    _monitor_log(
        "stage3_signals",
        "ok",
        "signals generated from predictions",
        metrics={
            "signals_total": int(len(selection.signals or [])),
            "signals_buy": int(signals_buy),
            "signals_sell": int(signals_sell),
        },
        sample_symbols=[str(getattr(s, "symbol", "")).upper() for s in (selection.signals or [])[:20] if str(getattr(s, "symbol", "")).strip()],
    )

    # If no signals pass thresholds, still choose monitor list by top prediction
    trade_universe: List[str] = [s.symbol for s in selection.signals]
    if (not trade_universe) and preds is not None and len(preds) > 0:
        idx = preds.index
        latest_dt = idx.get_level_values(0).max()
        latest = preds.xs(latest_dt, level=0).dropna().sort_values(ascending=False)
        monitor = latest.head(int(cfg.stage3.monitor_top_n_by_pred)).index.astype(str).str.upper().tolist()
        trade_universe = monitor

    trade_universe = list(dict.fromkeys([str(s).upper() for s in trade_universe if str(s).strip()]))

    write_csv_atomic(outdir / "qlib_preds_latest.csv", preds.reset_index().rename(columns={0: "pred"})) if preds is not None and len(preds) else write_csv_atomic(outdir / "qlib_preds_latest.csv", pd.DataFrame())
    write_csv_atomic(outdir / "trade_signals_latest.csv", selection.snapshot if selection.snapshot is not None else pd.DataFrame())
    write_csv_atomic(outdir / "universe_trade_today.csv", pd.DataFrame({"Symbol": trade_universe}))

    debug["trade_universe_count"] = len(trade_universe)
    debug["signals_count"] = len(selection.signals)
    debug["started_utc"] = t0.isoformat()
    debug["ended_utc"] = datetime.now(timezone.utc).isoformat()

    return debug
