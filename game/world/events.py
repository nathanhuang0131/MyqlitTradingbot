from game.core.state import CharacterState, GameState


def tile_event(state: GameState, tile: str) -> str | None:
    if tile == "town":
        return "You enter town and rest your spirit."
    if tile == "dungeon":
        state.flags.set("visited_dungeon", True)
        return "A chill from the dungeon gate reaches your bones."
    if tile == "shrine":
        state.flags.set("shrine_prayed", True)
        return "You offer a prayer."
    if tile == "kings_road":
        return "The King's Road leads toward destiny."
    return None


def recruitable_companion() -> CharacterState:
    return CharacterState(id="lady_airi", name="Lady Airi Valen", class_id="strategist", hp=90, mp=45, max_hp=90, max_mp=45, atk=10, defense=8, mag=14, mdef=12, agi=9, luck=11)
