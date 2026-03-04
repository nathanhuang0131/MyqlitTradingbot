from game.core.state import GameState


def initialize_route_flags(state: GameState) -> None:
    if state.route_id == "god_given":
        state.flags.set("goal_conquer_world", True)
    else:
        state.flags.set("goal_defeat_king_of_diablo", True)
