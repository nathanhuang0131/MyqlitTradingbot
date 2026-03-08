from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from qlib_tradingbot.core.models import Signal

VALID_BIAS = {"bullish", "bearish", "neutral"}
VALID_ACTION = {"hold", "trim", "exit", "add"}


def _line_kv(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None
    k, v = line.split(":", 1)
    return k.strip().upper(), v.strip()


def parse_feedback_text(text: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] = {}

    def _flush() -> None:
        symbol = str(current.get("SYMBOL", "")).upper().strip()
        if not symbol:
            return
        bias = str(current.get("BIAS", "Neutral")).strip().lower()
        action = str(current.get("ACTION", "Hold")).strip().lower()
        prob_raw = current.get("PROB", 0)
        try:
            prob = max(0.0, min(100.0, float(prob_raw)))
        except Exception:
            prob = 0.0
        if bias not in VALID_BIAS:
            bias = "neutral"
        if action not in VALID_ACTION:
            action = "hold"
        out[symbol] = {"bias": bias.title(), "prob": prob, "action": action.title()}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                _flush()
                current = {}
            continue
        kv = _line_kv(line)
        if kv is None:
            continue
        key, value = kv
        if key == "SYMBOL" and current.get("SYMBOL"):
            _flush()
            current = {}
        current[key] = value

    if current:
        _flush()
    return out


def load_bias_state(path: str | Path) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_bias_state(path: str | Path, state: dict[str, dict[str, Any]]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return p


def refresh_bias_state(data_dir: str | Path) -> dict[str, dict[str, Any]]:
    root = Path(data_dir)
    feedback_path = root / "llm_feedback_latest.txt"
    state_path = root / "llm_bias_state.json"

    if feedback_path.exists():
        parsed = parse_feedback_text(feedback_path.read_text(encoding="utf-8"))
        if parsed:
            write_bias_state(state_path, parsed)
    return load_bias_state(state_path)


def _is_conflicting(signal: Signal, bias: str) -> bool:
    b = bias.lower()
    if b == "neutral":
        return False
    if signal.side == "BUY":
        return b == "bearish"
    return b == "bullish"


def apply_feedback_gating(
    signals: list[Signal],
    state: dict[str, dict[str, Any]],
    *,
    prob_threshold: float = 60.0,
    neutral_size_factor: float = 0.5,
    default_dollars: float | None = None,
) -> list[Signal]:
    if not state:
        return signals

    out: list[Signal] = []
    for sig in signals:
        rule = state.get(sig.symbol.upper())
        if not rule:
            out.append(sig)
            continue

        bias = str(rule.get("bias", "Neutral"))
        prob = float(rule.get("prob", 0.0) or 0.0)
        if _is_conflicting(sig, bias):
            continue
        if prob < float(prob_threshold):
            continue

        if bias.lower() == "neutral":
            features = dict(sig.features or {})
            base_dollars = float(features.get("dollars", default_dollars or 0.0) or 0.0)
            if base_dollars > 0:
                features["dollars"] = base_dollars * float(neutral_size_factor)
            out.append(replace(sig, features=features))
            continue

        out.append(sig)
    return out
