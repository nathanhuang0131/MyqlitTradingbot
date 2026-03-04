from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from game.settings import CSV_DIR


class ClassRow(BaseModel):
    id: str
    name: str
    hp: int
    mp: int
    atk: int
    defense: int
    mag: int
    mdef: int
    agi: int
    luck: int


class CharacterRow(BaseModel):
    id: str
    name: str
    class_id: str
    faction: str
    role: str
    is_special: bool


class SkillRow(BaseModel):
    id: str
    name: str
    skill_type: str
    power: int
    mp_cost: int
    hit_rate: float
    status_effect: str


class MonsterRow(BaseModel):
    id: str
    name: str
    hp: int
    mp: int
    atk: int
    defense: int
    mag: int
    mdef: int
    agi: int
    luck: int
    exp: int
    gold: int
    drops: str


def _to_bool(v: str) -> bool:
    return str(v).lower() in {"1", "true", "yes"}


def _load_model_csv(path: Path, model: type[BaseModel]) -> list[BaseModel]:
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            normalized = {k: (None if v == "" else v) for k, v in raw.items()}
            for key, value in list(normalized.items()):
                if isinstance(value, str) and value.lower() in {"true", "false", "yes", "no"}:
                    normalized[key] = _to_bool(value)
            rows.append(model.model_validate(normalized))
    return rows


def load_database() -> dict[str, Any]:
    db: dict[str, Any] = {}
    db["classes"] = _load_model_csv(CSV_DIR / "classes.csv", ClassRow)
    db["characters"] = _load_model_csv(CSV_DIR / "characters.csv", CharacterRow)
    db["skills"] = _load_model_csv(CSV_DIR / "skills.csv", SkillRow)
    db["monsters"] = _load_model_csv(CSV_DIR / "monsters.csv", MonsterRow)
    for filename in [
        "skill_progression.csv",
        "items.csv",
        "equipment.csv",
        "artifacts.csv",
        "crafting_recipes.csv",
        "maps.csv",
        "events.csv",
        "dialogue.csv",
        "relationships.csv",
        "gifts.csv",
        "routes.csv",
    ]:
        with (CSV_DIR / filename).open(newline="", encoding="utf-8") as f:
            db[filename.removesuffix(".csv")] = list(csv.DictReader(f))
    return db
