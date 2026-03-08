from __future__ import annotations

from qlib_tradingbot.ModelLifecycle.registry import ModelCard


def select_best_model(cards: list[ModelCard]) -> ModelCard | None:
    if not cards:
        return None
    return sorted(
        cards,
        key=lambda c: (
            -float(c.metrics.get("pnl_sum", 0.0)),
            -float(c.metrics.get("win_rate", 0.0)),
            str(c.model_id),
        ),
    )[0]
