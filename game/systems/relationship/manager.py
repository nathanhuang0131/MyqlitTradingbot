from game.core.state import GameState, RelationshipState


def ensure_rel(state: GameState, npc_id: str) -> RelationshipState:
    if npc_id not in state.relationships:
        state.relationships[npc_id] = RelationshipState()
    return state.relationships[npc_id]


def apply_gift(state: GameState, npc_id: str, affection: int, trust: int) -> None:
    rel = ensure_rel(state, npc_id)
    rel.affection += affection
    rel.trust += trust
    rel.bond_level = min(5, (rel.affection + rel.trust) // 40)


def duo_skill_unlocked(state: GameState, npc_id: str) -> bool:
    return ensure_rel(state, npc_id).bond_level >= 3
