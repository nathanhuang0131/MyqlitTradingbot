from game.core.state import CharacterState
from game.systems.battle.formulas import skill_power


def level_skill(character: CharacterState, skill_id: str) -> bool:
    if character.skill_points <= 0:
        return False
    level = character.skills.get(skill_id, 0)
    if level >= 10:
        return False
    character.skills[skill_id] = level + 1
    character.skill_points -= 1
    return True


def get_scaled_power(base_power: int, lvl: int, fast: bool = False, hard: bool = False) -> int:
    return skill_power(base_power, lvl, fast_scaling=fast, hard_scaling=hard)
