from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from game.assets.core.state import CharacterState, GameState
from game.systems.battle import formulas


@dataclass
class BattleResult:
    victory: bool
    exp_gained: int
    gold_gained: int
    drops: dict[str, int]
    log: list[str]


def run_basic_battle(
    state: GameState,
    monsters: list[CharacterState],
    target_selector: Callable[[CharacterState, list[CharacterState], bool], int] | None = None,
    skill_rows: list[dict] | None = None,
    player_skill_id: str | None = None,
) -> BattleResult:
    log: list[str] = ["Battle started!"]
    party = state.active_party
    turn_order = sorted(party + monsters, key=lambda c: c.agi, reverse=True)
    skill_map = {str(row.get("id", "")).strip(): row for row in (skill_rows or [])}

    def select_skill(actor: CharacterState, is_player: bool) -> str:
        if is_player and player_skill_id:
            return player_skill_id
        if actor.skills:
            return next(iter(actor.skills.keys()))
        return "slash"

    def apply_status_tick(actor: CharacterState) -> None:
        if actor.hp <= 0:
            return
        if "poison" in actor.status:
            tick = formulas.poison_tick(actor.max_hp)
            actor.hp = max(0, actor.hp - tick)
            log.append(f"{actor.name} takes {tick} poison damage.")

    def apply_action(actor: CharacterState, target: CharacterState, skill_id: str) -> None:
        row = skill_map.get(skill_id, {})
        skill_name = str(row.get("name") or skill_id)
        skill_type = str(row.get("skill_type") or "physical").lower()
        power = int(float(row.get("power") or 10))
        mp_cost = int(float(row.get("mp_cost") or 0))
        status_effect = str(row.get("status_effect") or "").strip()

        if actor.mp < mp_cost:
            skill_type = "physical"
            power = 10
        else:
            actor.mp = max(0, actor.mp - mp_cost)

        if skill_type == "heal":
            amount = formulas.healing_amount(actor.mag, max(1, power))
            target.hp = min(target.max_hp, target.hp + amount)
            log.append(f"{actor.name} casts {skill_name} on {target.name} (+{amount} HP).")
            return

        if skill_type in {"magic", "status", "special"}:
            dmg = formulas.magic_damage(actor.mag, target.mdef, max(1, power))
        else:
            dmg = formulas.physical_damage(actor.atk, target.defense, max(1, power))

        target.hp = max(0, target.hp - dmg)
        log.append(f"{actor.name} uses {skill_name} on {target.name} for {dmg}.")
        if status_effect and target.hp > 0:
            first_status = status_effect.split("|")[0].strip()
            if first_status and first_status not in target.status:
                target.status.append(first_status)
                log.append(f"{target.name} is afflicted with {first_status}.")

    while any(p.hp > 0 for p in party) and any(m.hp > 0 for m in monsters):
        for actor in turn_order:
            if actor.hp <= 0:
                continue
            apply_status_tick(actor)
            if actor.hp <= 0:
                continue
            if actor in party:
                targets = [m for m in monsters if m.hp > 0]
                if not targets:
                    break
                idx = 0
                if target_selector:
                    idx = max(0, min(target_selector(actor, targets, True), len(targets) - 1))
                target = targets[idx]
                skill_id = select_skill(actor, actor.id == state.player.id)
                if skill_map.get(skill_id, {}).get("skill_type") == "heal":
                    ally_targets = [p for p in party if p.hp > 0]
                    heal_target = min(ally_targets, key=lambda c: c.hp / max(1, c.max_hp))
                    apply_action(actor, heal_target, skill_id)
                else:
                    apply_action(actor, target, skill_id)
            else:
                targets = [p for p in party if p.hp > 0]
                if not targets:
                    break
                idx = 0
                if target_selector:
                    idx = max(0, min(target_selector(actor, targets, False), len(targets) - 1))
                target = targets[idx]
                dmg = formulas.physical_damage(actor.atk, target.defense, power=8)
                target.hp = max(0, target.hp - dmg)
                log.append(f"{actor.name} attacks {target.name} for {dmg}.")
        turn_order = sorted(party + monsters, key=lambda c: c.agi, reverse=True)

    victory = any(p.hp > 0 for p in party)
    exp = sum(24 for _ in monsters)
    gold = sum(12 for _ in monsters)
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
