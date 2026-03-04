from game.core.state import GameState


def add_item(state: GameState, item_id: str, qty: int = 1) -> None:
    state.inventory.items[item_id] = state.inventory.items.get(item_id, 0) + qty


def use_item(state: GameState, item_id: str) -> bool:
    if state.inventory.items.get(item_id, 0) <= 0:
        return False
    state.inventory.items[item_id] -= 1
    return True
