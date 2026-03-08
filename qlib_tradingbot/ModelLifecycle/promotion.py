from __future__ import annotations

from qlib_tradingbot.ModelLifecycle.registry import ModelRegistry


def promote_if_eligible(
    registry: ModelRegistry,
    model_id: str,
    *,
    min_win_rate: float = 0.55,
    min_pnl_sum: float = 0.0,
) -> bool:
    card = registry.get(model_id)
    if card is None:
        return False
    win = float(card.metrics.get("win_rate", 0.0))
    pnl = float(card.metrics.get("pnl_sum", 0.0))
    if win < float(min_win_rate):
        return False
    if pnl < float(min_pnl_sum):
        return False
    registry.set_production(model_id)
    return True
