from __future__ import annotations

from dataclasses import dataclass

from game.core.state import CharacterState, GameState
from game.systems.battle import formulas


@dataclass
class BattleResult:
    victory: bool
    exp_gained: int
    gold_gained: int
    drops: dict[str, int]
    log: list[str]


def run_basic_battle(state: GameState, monsters: list[CharacterState]) -> BattleResult:
    log: list[str] = ["Battle started!"]
    party = state.active_party
    turn_order = sorted(party + monsters, key=lambda c: c.agi, reverse=True)
    while any(p.hp > 0 for p in party) and any(m.hp > 0 for m in monsters):
        for actor in turn_order:
            if actor.hp <= 0:
                continue
            if actor in party:
                targets = [m for m in monsters if m.hp > 0]
                if not targets:
                    break
                target = targets[0]
                dmg = formulas.physical_damage(actor.atk, target.defense, power=11)
                target.hp = max(0, target.hp - dmg)
                log.append(f"{actor.name} hits {target.name} for {dmg}.")
            else:
                targets = [p for p in party if p.hp > 0]
                if not targets:
                    break
                target = targets[0]
                dmg = formulas.physical_damage(actor.atk, target.defense, power=8)
                target.hp = max(0, target.hp - dmg)
                log.append(f"{actor.name} attacks {target.name} for {dmg}.")
        turn_order = sorted(party + monsters, key=lambda c: c.agi, reverse=True)

    victory = any(p.hp > 0 for p in party)
    exp = sum(24 for m in monsters)
    gold = sum(12 for m in monsters)
    drops = {"potion": 1} if victory else {}

    if victory:
        for member in party:
            if member.hp <= 0:
                member.hp = 1
        state.inventory.gold += gold
        state.inventory.items["potion"] = state.inventory.items.get("potion", 0) + 1
        state.player.exp += exp
        state.player.skill_points += 1
    return BattleResult(victory=victory, exp_gained=exp if victory else 0, gold_gained=gold if victory else 0, drops=drops, log=log)
