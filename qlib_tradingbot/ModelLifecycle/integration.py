from __future__ import annotations

from pathlib import Path

from qlib_tradingbot.ModelLifecycle.registry import ModelRegistry


def load_selected_model_thresholds(registry_dir: str | Path) -> tuple[float | None, float | None]:
    registry = ModelRegistry(registry_dir)
    model_id = registry.get_production()
    if not model_id:
        return None, None
    card = registry.get(model_id)
    if card is None:
        return None, None
    buy = card.params.get("signal_threshold_buy")
    sell = card.params.get("signal_threshold_sell")
    return (None if buy is None else float(buy), None if sell is None else float(sell))
