from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


def append_csv_row_safe(path: str | Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_header = (not p.exists()) or p.stat().st_size == 0
    with p.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fieldnames})


@dataclass(frozen=True)
class StageEvent:
    run_id: str
    strategy: str
    iteration: int | None
    stage: str
    status: str
    ts_utc: str
    message: str
    metrics: dict[str, Any] = field(default_factory=dict)
    sample_symbols: list[str] = field(default_factory=list)
    error: str | None = None


class StageMonitor:
    CSV_COLUMNS = [
        "run_id",
        "ts_utc",
        "strategy",
        "iteration",
        "stage",
        "status",
        "message",
        "metrics_json",
        "sample_symbols_json",
        "error",
    ]

    def __init__(self) -> None:
        self.run_id: str = ""
        self.strategy: str = ""
        self.iteration: int | None = None
        self._events: list[StageEvent] = []
        self._errors: list[str] = []

    def start_run(self, strategy: str, iteration: int | None) -> str:
        try:
            self.strategy = str(strategy or "").strip() or "unknown"
            self.iteration = iteration
            self.run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
            self._events = []
            self._errors = []
        except Exception as exc:
            self._errors.append(f"start_run_error: {exc}")
            if not self.run_id:
                self.run_id = f"monitor-fallback-{uuid4().hex[:8]}"
        return self.run_id

    def log(
        self,
        stage: str,
        status: str,
        message: str,
        metrics: dict[str, Any] | None = None,
        sample_symbols: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        try:
            event = StageEvent(
                run_id=self.run_id or f"monitor-fallback-{uuid4().hex[:8]}",
                strategy=self.strategy or "unknown",
                iteration=self.iteration,
                stage=str(stage or "").strip() or "unknown_stage",
                status=str(status or "").strip().lower() or "ok",
                ts_utc=_utc_now_iso(),
                message=str(message or ""),
                metrics=_jsonable(metrics or {}) or {},
                sample_symbols=[str(s).upper() for s in (sample_symbols or []) if str(s).strip()],
                error=str(error) if error else None,
            )
            self._events.append(event)
        except Exception as exc:
            self._errors.append(f"log_error:{type(exc).__name__}:{exc}")

    def finalize(self) -> dict[str, Any]:
        latest_by_stage: dict[str, dict[str, Any]] = {}
        for e in self._events:
            latest_by_stage[e.stage] = asdict(e)
        return {
            "run_id": self.run_id,
            "strategy": self.strategy,
            "iteration": self.iteration,
            "events_count": len(self._events),
            "errors": list(self._errors),
            "latest_by_stage": latest_by_stage,
        }

    def flush_csv(self, path: str | Path = "Data/stage_trace.csv") -> None:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            for e in self._events:
                append_csv_row_safe(
                    p,
                    self.CSV_COLUMNS,
                    {
                        "run_id": e.run_id,
                        "ts_utc": e.ts_utc,
                        "strategy": e.strategy,
                        "iteration": e.iteration if e.iteration is not None else "",
                        "stage": e.stage,
                        "status": e.status,
                        "message": e.message,
                        "metrics_json": json.dumps(e.metrics, separators=(",", ":"), default=str),
                        "sample_symbols_json": json.dumps(e.sample_symbols, separators=(",", ":"), default=str),
                        "error": e.error or "",
                    },
                )
        except Exception as exc:
            self._errors.append(f"flush_csv_error:{type(exc).__name__}:{exc}")

    def flush_jsonl(self, path: str | Path = "Data/stage_trace.jsonl") -> None:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                for e in self._events:
                    f.write(json.dumps(asdict(e), default=str) + "\n")
        except Exception as exc:
            self._errors.append(f"flush_jsonl_error:{type(exc).__name__}:{exc}")
