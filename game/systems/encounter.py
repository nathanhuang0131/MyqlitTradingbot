from __future__ import annotations

from dataclasses import dataclass, field

from game.assets.core.rng import RNGService

DANGER_TILE_IDS = {"danger", "kings_road"}
ENCOUNTER_TABLE: dict[str, list[str]] = {
    "danger_default": ["goblin"],
    "ruins_scouts": ["goblin", "goblin"],
}


@dataclass
class EncounterSystem:
    chance: float = 0.15
    danger_tiles: set[str] = field(default_factory=lambda: set(DANGER_TILE_IDS))
    force_next: bool = False
    last_tile_id: str = ""
    last_is_danger: bool = False
    last_roll: float | None = None
    last_triggered: bool = False

    def force_next_encounter(self) -> None:
        self.force_next = True

    def roll_for_tile(self, tile_id: str, rng: RNGService) -> bool:
        self.last_tile_id = tile_id
        self.last_is_danger = tile_id in self.danger_tiles

        if self.force_next:
            self.force_next = False
            self.last_roll = -1.0
            self.last_triggered = True
            return True

        if not self.last_is_danger:
            self.last_roll = None
            self.last_triggered = False
            return False

        roll = rng.roll()
        self.last_roll = roll
        self.last_triggered = roll < self.chance
        return self.last_triggered

