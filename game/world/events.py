from __future__ import annotations

from game.assets.core.rng import RNGService
from game.assets.core.state import CharacterState


def roll_danger_encounter(rng: RNGService, chance: float) -> bool:
    return rng.chance(chance)


def recruitable_companion() -> CharacterState:
    return CharacterState(
        id="lady_airi",
        name="Lady Airi Valen",
        class_id="healer",
        hp=90,
        mp=45,
        max_hp=90,
        max_mp=45,
        atk=10,
        defense=8,
        mag=14,
        mdef=12,
        agi=9,
        luck=11,
        skills={"heal": 1},
    )
