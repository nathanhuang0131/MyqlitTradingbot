from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qlib_tradingbot.Utils.timezone_utils import to_new_york


def _safe_json_load(text: str) -> dict[str, Any]:
    try:
        obj = json.loads(text or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _latest_stage_run_id(stage_path: Path) -> str | None:
    if not stage_path.exists():
        return None
    try:
        df = pd.read_csv(stage_path)
    except Exception:
        return None
    if df.empty or "run_id" not in df.columns:
        return None
    runs = [str(x) for x in df["run_id"].dropna().tolist() if str(x).strip()]
    return runs[-1] if runs else None


def _load_stage_events(stage_path: Path, run_id: str) -> list[dict[str, Any]]:
    if not stage_path.exists():
        return []
    try:
        df = pd.read_csv(stage_path)
    except Exception:
        return []
    if df.empty:
        return []
    if "run_id" in df.columns:
        df = df[df["run_id"].astype(str) == str(run_id)]
    events: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        metrics = _safe_json_load(str(row.get("metrics_json", "") or "{}"))
        events.append(
            {
                "run_id": str(row.get("run_id", "")),
                "strategy": str(row.get("strategy", "")),
                "stage": str(row.get("stage", "")),
                "status": str(row.get("status", "")),
                "message": str(row.get("message", "")),
                "ts_utc": str(row.get("ts_utc", "")),
                "error": str(row.get("error", "")),
                "metrics": metrics,
            }
        )
    return events


def _latest_by_stage(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for e in events:
        out[str(e.get("stage", ""))] = e
    return out


def _load_run_log_rows(data_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    jsonl = data_dir / "run_log.jsonl"
    if jsonl.exists():
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue

    csv_path = data_dir / "run_log.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            df = pd.DataFrame()
        if not df.empty:
            rows.extend(df.to_dict(orient="records"))
    return rows


def analyze_last_run(data_dir: Path, run_id: str | None = None) -> dict[str, Any]:
    stage_path = data_dir / "stage_trace.csv"
    rid = str(run_id or _latest_stage_run_id(stage_path) or "").strip()
    if not rid:
        return {
            "run_id": "",
            "top_reason_codes": ["NO_TRACE_DATA"],
            "explanations": ["No stage trace data found."],
            "counters": {},
        }

    events = _load_stage_events(stage_path, rid)
    by_stage = _latest_by_stage(events)
    strategy = str((events[-1].get("strategy") if events else "") or "").strip().lower()

    gate = by_stage.get("stage0_gate", {})
    gate_metrics = dict(gate.get("metrics") or {})
    stage1 = by_stage.get("stage1_universe", {})
    stage1_metrics = dict(stage1.get("metrics") or {})
    stage2 = by_stage.get("stage2_filters", {})
    stage2_metrics = dict(stage2.get("metrics") or {})
    stage3_sig = by_stage.get("stage3_signals", {})
    sig_metrics = dict(stage3_sig.get("metrics") or {})
    stage3_exec = by_stage.get("stage3_execution", {})
    exec_metrics = dict(stage3_exec.get("metrics") or {})

    market_open = bool(gate_metrics.get("market_open", False))
    within_window = bool(gate_metrics.get("within_window", True))
    stage1_size = int(stage1_metrics.get("stage1_universe_size", 0) or 0)
    signals_total = int(sig_metrics.get("signals_total", 0) or 0)
    orders_attempted = int(exec_metrics.get("orders_attempted", 0) or 0)
    orders_submitted = int(exec_metrics.get("orders_submitted", 0) or 0)
    orders_failed = int(exec_metrics.get("orders_failed", 0) or 0)
    dry_run = bool(exec_metrics.get("dry_run", False))
    monitor_stage = by_stage.get("stage3_monitor_universe", {})
    monitor_metrics = dict(monitor_stage.get("metrics") or {})
    final_universe_size = int(monitor_metrics.get("final_universe_size", 0) or 0)
    rejection_reasons = dict(exec_metrics.get("rejection_reasons") or {})

    reason_codes: list[str] = []
    explanations: list[str] = []

    run_log_rows = _load_run_log_rows(data_dir)
    last_status = ""
    if run_log_rows:
        last_status = str(run_log_rows[-1].get("status", "")).strip().lower()

    if not market_open or last_status == "market_closed":
        reason_codes.append("MARKET_CLOSED")
        explanations.append("Market was closed during the run.")
    if not within_window:
        reason_codes.append("OUTSIDE_WINDOW")
        explanations.append("Run was outside the configured NY trading window.")
    if stage1_size <= 0:
        reason_codes.append("UNIVERSE_EMPTY")
        explanations.append("Stage-1 universe was empty.")
    if "final_universe_size" in monitor_metrics and final_universe_size <= 0 and stage1_size > 0:
        reason_codes.append("UNIVERSE_EMPTY")
        explanations.append("Filtered universe for execution was empty.")
    if signals_total <= 0:
        reason_codes.append("NO_SIGNALS")
        explanations.append("No signals were generated.")
    if dry_run:
        reason_codes.append("DRY_RUN_TRUE")
        explanations.append("Dry-run mode prevented broker submissions.")
    if orders_attempted > 0 and orders_submitted == 0 and rejection_reasons:
        reason_codes.append("ORDERS_REJECTED")
        top_err = sorted(rejection_reasons.items(), key=lambda kv: int(kv[1]), reverse=True)[:3]
        explanations.append(f"Orders were attempted but rejected: {top_err}.")
    if orders_attempted > 0 and orders_submitted == 0 and not rejection_reasons:
        reason_codes.append("BROKER_CLIENT_MISSING")
        explanations.append("Orders were attempted but no broker submission occurred.")

    if strategy == "intraday":
        ts = str(gate.get("ts_utc", "") or "")
        try:
            dt_utc = pd.Timestamp(ts).to_pydatetime()
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=datetime.utcnow().astimezone().tzinfo)
            ny = to_new_york(dt_utc)
        except Exception:
            ny = None
        if ny is not None and (ny.hour, ny.minute) < (15, 55):
            reason_codes.append("NOT_EOD_YET")
            explanations.append("Intraday flatten triggers only after 15:55 NY.")
        if stage1_size <= 0:
            reason_codes.append("NO_POSITIONS_TO_FLATTEN")
            explanations.append("Intraday flatten found no held positions to close.")

    orders_path = data_dir / "orders.csv"
    orders_rows = 0
    if orders_path.exists():
        try:
            orders_df = pd.read_csv(orders_path)
            orders_rows = int(len(orders_df))
        except Exception:
            orders_rows = 0

    trades_path = data_dir / "trades_ledger.csv"
    ledger_rows = 0
    if trades_path.exists():
        try:
            ledger_rows = int(len(pd.read_csv(trades_path)))
        except Exception:
            ledger_rows = 0

    # Preserve first-seen ordering, de-duped.
    deduped_codes: list[str] = []
    for code in reason_codes:
        if code not in deduped_codes:
            deduped_codes.append(code)

    if not deduped_codes:
        deduped_codes = ["NO_BLOCKERS_FOUND"]
        explanations.append("No obvious suppressor found in trace artifacts.")

    return {
        "run_id": rid,
        "strategy": strategy,
        "top_reason_codes": deduped_codes,
        "explanations": explanations,
        "counters": {
            "market_open": market_open,
            "within_window": within_window,
            "stage1_universe_size": stage1_size,
            "stage2_input_size": int(stage2_metrics.get("stage2_input_size", 0) or 0),
            "stage2_output_size": int(stage2_metrics.get("stage2_output_size", 0) or 0),
            "signals_total": signals_total,
            "orders_attempted": orders_attempted,
            "orders_submitted": orders_submitted,
            "orders_failed": orders_failed,
            "dry_run": dry_run,
            "orders_rows": orders_rows,
            "trades_ledger_rows": ledger_rows,
            "rejection_reasons": rejection_reasons,
        },
    }
