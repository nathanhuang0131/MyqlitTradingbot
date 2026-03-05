from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RiskLimits:
    max_positions: int = 10
    max_exposure: float = 1.0
    min_confidence: float = 0.0


def apply_portfolio_constraints(signal_frame: pd.DataFrame, limits: RiskLimits) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (accepted, rejected) by confidence, position count, and exposure budget."""
    if signal_frame is None or signal_frame.empty:
        empty = pd.DataFrame(columns=list(signal_frame.columns) + ["rejection_reason"] if signal_frame is not None else ["rejection_reason"])
        return pd.DataFrame(columns=getattr(signal_frame, "columns", [])), empty

    frame = signal_frame.copy()
    frame["confidence"] = pd.to_numeric(frame.get("confidence", 0.0), errors="coerce").fillna(0.0)
    frame["alpha"] = pd.to_numeric(frame.get("alpha", 0.0), errors="coerce").fillna(0.0)
    frame["weight"] = frame["confidence"].abs()

    rejected = frame[frame["confidence"] < float(limits.min_confidence)].copy()
    rejected["rejection_reason"] = "below_min_confidence"

    candidates = frame[frame["confidence"] >= float(limits.min_confidence)].copy()
    candidates = candidates.sort_values("alpha", ascending=False).reset_index(drop=True)

    accepted_rows = []
    exposure = 0.0
    for _, row in candidates.iterrows():
        if len(accepted_rows) >= int(limits.max_positions):
            rej = row.to_dict()
            rej["rejection_reason"] = "max_positions"
            rejected = pd.concat([rejected, pd.DataFrame([rej])], ignore_index=True)
            continue
        next_exposure = exposure + float(row.get("weight", 0.0))
        if next_exposure > float(limits.max_exposure):
            rej = row.to_dict()
            rej["rejection_reason"] = "max_exposure"
            rejected = pd.concat([rejected, pd.DataFrame([rej])], ignore_index=True)
            continue
        exposure = next_exposure
        accepted_rows.append(row.to_dict())

    accepted = pd.DataFrame(accepted_rows).drop(columns=["weight"], errors="ignore")
    rejected = rejected.drop(columns=["weight"], errors="ignore")
    return accepted.reset_index(drop=True), rejected.reset_index(drop=True)


__all__ = ["RiskLimits", "apply_portfolio_constraints"]
