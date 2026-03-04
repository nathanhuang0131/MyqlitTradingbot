from __future__ import annotations


def hit_chance(acc: int, eva: int, skill_hit_rate: float = 1.0) -> float:
    return max(0.05, min(0.98, (0.75 + (acc - eva) * 0.01) * skill_hit_rate))


def crit_chance(luck: int, enemy_luck: int) -> float:
    return max(0.01, min(0.5, 0.05 + (luck - enemy_luck) * 0.003))


def physical_damage(atk: int, defense: int, power: int, crit: bool = False) -> int:
    base = max(1, (atk * power // 10) - defense)
    return int(base * (1.7 if crit else 1.0))


def magic_damage(mag: int, mdef: int, power: int) -> int:
    return max(1, (mag * power // 10) - mdef // 2)


def healing_amount(mag: int, power: int) -> int:
    return max(1, mag * power // 8)


def status_chance(base: float, level_delta: int, resist: float = 0.0) -> float:
    return max(0.0, min(1.0, base + level_delta * 0.01 - resist))


def status_duration(base_turns: int, skill_level: int) -> int:
    return max(1, base_turns + skill_level // 3)


def poison_tick(max_hp: int, stacks: int = 1) -> int:
    return max(1, int(max_hp * 0.05 * stacks))


def exp_curve(level: int) -> int:
    return int(40 * (level**2) + 20 * level)


def skill_power(base_power: int, skill_level: int, fast_scaling: bool = False, hard_scaling: bool = False) -> int:
    scale = 0.12 if fast_scaling else 0.07
    if hard_scaling:
        scale += 0.06
    return int(base_power * (1 + skill_level * scale))
