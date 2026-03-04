from game.core.state import CharacterState, GameState
from game.settings import MAX_PARTY_SIZE


def recruit(state: GameState, companion: CharacterState) -> bool:
    if len(state.active_party) >= MAX_PARTY_SIZE:
        return False
    state.party.append(companion)
    return True
