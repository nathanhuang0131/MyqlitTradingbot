from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from qlib_tradingbot.Decision.models import DecisionRecord

JOURNAL_COLUMNS = [
    "symbol",
    "strategy_id",
    "model_id",
    "run_id",
    "correlation_id",
    "entry_timestamp",
    "entry_thesis",
    "entry_qlib_score",
    "entry_llm_bias",
    "entry_llm_prob",
    "expected_horizon",
    "target",
    "stop",
    "invalidation_condition",
    "review_cadence",
    "latest_review_timestamp",
    "latest_status",
    "latest_recommended_action",
    "reason_summary",
]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_decision_trace(data_dir: Path | str, records: Iterable[DecisionRecord]) -> Path:
    out = Path(data_dir) / "decision_trace.jsonl"
    _ensure_parent(out)
    with out.open("a", encoding="utf-8") as f:
        for r in records:
            payload = asdict(r)
            payload["reasons"] = list(payload.get("reasons", []))
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return out


def upsert_position_journal(
    data_dir: Path | str,
    records: Iterable[DecisionRecord],
    *,
    expected_horizon: str,
    entry_thesis: str,
    target: float,
    stop: float,
    invalidation_condition: str = "stop_hit_or_thesis_invalidated",
    review_cadence: str = "1D",
) -> Path:
    out = Path(data_dir) / "position_journal.csv"
    _ensure_parent(out)
    existing = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=JOURNAL_COLUMNS)
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for r in records:
        if str(r.final_action).lower() not in {"buy", "reduce", "sell"}:
            continue
        status = "on_track" if str(r.final_action).lower() in {"buy", "reduce"} else "invalidated"
        rows.append(
            {
                "symbol": r.symbol,
                "strategy_id": r.strategy_id,
                "model_id": r.model_id,
                "run_id": r.run_id,
                "correlation_id": r.correlation_id,
                "entry_timestamp": r.ts_utc,
                "entry_thesis": entry_thesis,
                "entry_qlib_score": r.qlib_alpha,
                "entry_llm_bias": r.llm_bias,
                "entry_llm_prob": r.llm_probability,
                "expected_horizon": expected_horizon,
                "target": float(target),
                "stop": float(stop),
                "invalidation_condition": invalidation_condition,
                "review_cadence": review_cadence,
                "latest_review_timestamp": now,
                "latest_status": status,
                "latest_recommended_action": str(r.final_action),
                "reason_summary": ";".join(r.reasons),
            }
        )
    if rows:
        new_df = pd.DataFrame(rows, columns=JOURNAL_COLUMNS)
        if existing.empty:
            combined = new_df.copy()
        else:
            combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.sort_values(["symbol", "entry_timestamp"]).drop_duplicates(subset=["symbol"], keep="last")
    else:
        combined = existing
    combined.to_csv(out, index=False)
    return out


def _parse_days(text: str) -> float:
    s = str(text or "1D").strip().upper()
    if s.endswith("D"):
        try:
            return max(1.0, float(s[:-1] or 1.0))
        except Exception:
            return 1.0
    if s.endswith("H"):
        try:
            return max(1.0 / 24.0, float(s[:-1] or 24.0) / 24.0)
        except Exception:
            return 1.0
    return 1.0


def review_position_health(data_dir: Path | str, *, now_utc: datetime | None = None) -> pd.DataFrame:
    root = Path(data_dir)
    journal_path = root / "position_journal.csv"
    health_path = root / "position_health.csv"
    if not journal_path.exists():
        pd.DataFrame(columns=["symbol", "latest_status", "latest_recommended_action", "reason_summary"]).to_csv(health_path, index=False)
        return pd.read_csv(health_path)
    journal = pd.read_csv(journal_path)
    now = now_utc or datetime.now(timezone.utc)
    out_rows = []
    for _, row in journal.iterrows():
        entry_ts = pd.to_datetime(row.get("entry_timestamp"), utc=True, errors="coerce")
        review_ts = pd.to_datetime(row.get("latest_review_timestamp"), utc=True, errors="coerce")
        entry_score = float(pd.to_numeric(row.get("entry_qlib_score"), errors="coerce") or 0.0)
        horizon_days = _parse_days(str(row.get("expected_horizon", "1D")))
        age_days = float((now - entry_ts.to_pydatetime()).total_seconds() / 86400.0) if pd.notna(entry_ts) else 0.0
        days_since_review = float((now - review_ts.to_pydatetime()).total_seconds() / 86400.0) if pd.notna(review_ts) else 999.0

        status = "on_track"
        reasons: list[str] = []
        if days_since_review > max(1.0, horizon_days):
            status = "watch"
            reasons.append("unreviewed")
        if age_days > horizon_days * 2.0:
            status = "risk"
            reasons.append("stale_horizon")
        if entry_score < 0:
            status = "invalidated"
            reasons.append("thesis_drift_negative_entry_score")
        out_rows.append(
            {
                "symbol": row.get("symbol", ""),
                "strategy_id": row.get("strategy_id", ""),
                "model_id": row.get("model_id", ""),
                "run_id": row.get("run_id", ""),
                "correlation_id": row.get("correlation_id", ""),
                "entry_timestamp": row.get("entry_timestamp", ""),
                "expected_horizon": row.get("expected_horizon", ""),
                "latest_review_timestamp": now.isoformat(),
                "latest_status": status,
                "latest_recommended_action": row.get("latest_recommended_action", ""),
                "reason_summary": "|".join(reasons) if reasons else "ok",
            }
        )
    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(health_path, index=False)
    journal = journal.copy()
    if not out_df.empty:
        m = out_df.set_index("symbol")
        for idx, r in journal.iterrows():
            sym = str(r.get("symbol", ""))
            if sym in m.index:
                journal.at[idx, "latest_review_timestamp"] = m.loc[sym, "latest_review_timestamp"]
                journal.at[idx, "latest_status"] = m.loc[sym, "latest_status"]
                journal.at[idx, "reason_summary"] = m.loc[sym, "reason_summary"]
    journal.to_csv(journal_path, index=False)
    return out_df
