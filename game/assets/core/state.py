from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from game.settings import MAX_PARTY_SIZE, ROUNDS_PER_DAY


class CharacterState(BaseModel):
    id: str
    name: str
    class_id: str
    level: int = 1
    exp: int = 0
    hp: int = 100
    mp: int = 30
    max_hp: int = 100
    max_mp: int = 30
    atk: int = 12
    defense: int = 8
    mag: int = 10
    mdef: int = 8
    agi: int = 10
    luck: int = 8
    status: list[str] = Field(default_factory=list)
    skill_points: int = 0
    skills: dict[str, int] = Field(default_factory=dict)


class RelationshipState(BaseModel):
    affection: int = 0
    trust: int = 0
    bond_level: int = 0


class StoryFlagStore(BaseModel):
    flags: dict[str, bool] = Field(default_factory=dict)

    def set(self, key: str, value: bool = True) -> None:
        self.flags[key] = value

    def check(self, key: str) -> bool:
        return self.flags.get(key, False)


class InventoryState(BaseModel):
    items: dict[str, int] = Field(default_factory=dict)
    materials: dict[str, int] = Field(default_factory=dict)
    gold: int = 100
    artifact_owners: dict[str, str] = Field(default_factory=dict)


class GameState(BaseModel):
    day: int = 1
    rounds_remaining_today: int = ROUNDS_PER_DAY
    route_id: str = "ordinary"
    player: CharacterState
    party: list[CharacterState] = Field(default_factory=list)
    inventory: InventoryState = Field(default_factory=InventoryState)
    relationships: dict[str, RelationshipState] = Field(default_factory=dict)
    flags: StoryFlagStore = Field(default_factory=StoryFlagStore)
    position: tuple[int, int] = (2, 2)
    map_id: str = "starter_field"

    def consume_round(self) -> None:
        self.rounds_remaining_today -= 1
        if self.rounds_remaining_today <= 0:
            self.day += 1
            self.rounds_remaining_today = ROUNDS_PER_DAY

    @property
    def active_party(self) -> list[CharacterState]:
        return [self.player] + self.party[: max(0, MAX_PARTY_SIZE - 1)]


@dataclass
class RuntimeContext:
    db: dict[str, Any]
    state: GameState
