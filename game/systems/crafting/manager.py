from game.core.state import GameState


def craft(state: GameState, recipe: dict) -> bool:
    for item_id, req in recipe.items():
        if state.inventory.materials.get(item_id, 0) < req:
            return False
    for item_id, req in recipe.items():
        state.inventory.materials[item_id] -= req
    return True
