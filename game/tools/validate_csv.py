from __future__ import annotations

import csv
import sys
from pathlib import Path

from game.settings import CSV_DIR
from game.systems.encounter import ENCOUNTER_TABLE

REQUIRED = {
    "classes.csv": ["id", "name", "hp", "mp", "atk", "defense", "mag", "mdef", "agi", "luck"],
    "characters.csv": ["id", "name", "class_id", "faction", "role", "is_special"],
    "skills.csv": ["id", "name", "skill_type", "power", "mp_cost", "hit_rate", "status_effect"],
    "monsters.csv": ["id", "name", "hp", "mp", "atk", "defense", "mag", "mdef", "agi", "luck", "exp", "gold", "drops"],
    "artifacts.csv": ["id", "name", "owner_hint", "unique", "craftable"],
    "events.csv": [
        "id",
        "map_id",
        "x",
        "y",
        "trigger",
        "flag_set",
        "flag_required",
        "once",
        "dialogue_start_id",
        "encounter_id",
        "recruit_id",
        "next_event_id",
        "chapter",
    ],
    "dialogue.csv": [
        "id",
        "speaker",
        "text",
        "next_id",
        "choice_group",
        "choice_label",
        "flag_required",
        "set_flag",
        "affection_delta",
        "trust_delta",
        "item_id",
        "item_delta",
    ],
    "gifts.csv": ["id", "item_id", "target_npc", "affection_delta", "trust_delta"],
    "relationships.csv": ["npc_id", "likes", "dislikes", "bond1", "bond2", "bond3", "duo_skill"],
    "routes.csv": ["id", "name", "win_condition", "lose_condition", "start_flags"],
    "bond_thresholds.csv": ["bond_level", "min_affection", "min_trust"],
    "skill_progression.csv": ["class_id", "level", "skill_id"],
}

NUMERIC = {
    "classes.csv": ["hp", "mp", "atk", "defense", "mag", "mdef", "agi", "luck"],
    "skills.csv": ["power", "mp_cost", "hit_rate"],
    "monsters.csv": ["hp", "exp", "gold"],
    "events.csv": ["x", "y", "chapter"],
    "dialogue.csv": ["affection_delta", "trust_delta", "item_delta"],
    "gifts.csv": ["affection_delta", "trust_delta"],
    "relationships.csv": ["bond1", "bond2", "bond3"],
    "bond_thresholds.csv": ["bond_level", "min_affection", "min_trust"],
    "skill_progression.csv": ["level"],
}


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def validate(csv_dir: Path | None = None, emit: bool = False) -> tuple[int, list[str]]:
    base = csv_dir or CSV_DIR
    errors: list[str] = []
    rows_by_file: dict[str, list[dict[str, str]]] = {}

    for file, cols in REQUIRED.items():
        path = base / file
        if not path.exists():
            errors.append(f"Missing file: {file}")
            continue

        rows = _read_rows(path)
        rows_by_file[file] = rows

        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            missing = [c for c in cols if c not in headers]
            if missing:
                errors.append(f"{file} missing columns: {missing}")

        for i, row in enumerate(rows, 2):
            for col in NUMERIC.get(file, []):
                value = row.get(col, "")
                if _is_blank(value):
                    continue
                try:
                    float(value)
                except Exception:
                    errors.append(f"{file}:{i} invalid numeric {col}={value}")

    dialogue_rows = rows_by_file.get("dialogue.csv", [])
    dialogue_ids = {r.get("id", "").strip() for r in dialogue_rows if not _is_blank(r.get("id"))}
    for i, row in enumerate(dialogue_rows, 2):
        node_id = (row.get("id") or "").strip()
        next_id = (row.get("next_id") or "").strip()
        if _is_blank(node_id):
            errors.append(f"dialogue.csv:{i} blank id")
        if next_id and next_id not in dialogue_ids:
            errors.append(f"dialogue.csv:{i} next_id references missing dialogue id '{next_id}'")

    event_rows = rows_by_file.get("events.csv", [])
    event_ids = {r.get("id", "").strip() for r in event_rows if not _is_blank(r.get("id"))}
    monster_ids = {r.get("id", "").strip() for r in rows_by_file.get("monsters.csv", []) if not _is_blank(r.get("id"))}
    for i, row in enumerate(event_rows, 2):
        event_id = (row.get("id") or "").strip()
        if _is_blank(event_id):
            errors.append(f"events.csv:{i} blank id")
        dialogue_start_id = (row.get("dialogue_start_id") or "").strip()
        if dialogue_start_id and dialogue_start_id not in dialogue_ids:
            errors.append(f"events.csv:{i} dialogue_start_id references missing dialogue id '{dialogue_start_id}'")
        next_event_id = (row.get("next_event_id") or "").strip()
        if next_event_id and next_event_id not in event_ids:
            errors.append(f"events.csv:{i} next_event_id references missing event id '{next_event_id}'")
        encounter_id = (row.get("encounter_id") or "").strip()
        if encounter_id and encounter_id not in ENCOUNTER_TABLE:
            errors.append(f"events.csv:{i} encounter_id references missing encounter table id '{encounter_id}'")

    for encounter_id, spawn_list in ENCOUNTER_TABLE.items():
        for mon_id in spawn_list:
            if mon_id not in monster_ids:
                errors.append(f"encounter table '{encounter_id}' references missing monster id '{mon_id}'")

    relation_rows = rows_by_file.get("relationships.csv", [])
    npc_ids = {r.get("npc_id", "").strip() for r in relation_rows if not _is_blank(r.get("npc_id"))}
    for i, row in enumerate(rows_by_file.get("gifts.csv", []), 2):
        npc = (row.get("target_npc") or "").strip()
        if npc and npc not in npc_ids:
            errors.append(f"gifts.csv:{i} target_npc references missing relationships npc_id '{npc}'")

    class_ids = {r.get("id", "").strip() for r in rows_by_file.get("classes.csv", []) if not _is_blank(r.get("id"))}
    skill_ids = {r.get("id", "").strip() for r in rows_by_file.get("skills.csv", []) if not _is_blank(r.get("id"))}
    for i, row in enumerate(rows_by_file.get("skill_progression.csv", []), 2):
        class_id = (row.get("class_id") or "").strip()
        skill_id = (row.get("skill_id") or "").strip()
        if class_id and class_id not in class_ids:
            errors.append(f"skill_progression.csv:{i} class_id references missing class '{class_id}'")
        if skill_id and skill_id not in skill_ids:
            errors.append(f"skill_progression.csv:{i} skill_id references missing skill '{skill_id}'")

    for name, rows in rows_by_file.items():
        key = "id"
        if name == "relationships.csv":
            key = "npc_id"
        seen: set[str] = set()
        for i, row in enumerate(rows, 2):
            value = (row.get(key) or "").strip()
            if not value:
                continue
            if value in seen:
                errors.append(f"{name}:{i} duplicate {key} '{value}'")
            seen.add(value)

    if emit:
        if errors:
            print("CSV validation failed:")
            for e in errors:
                print(" -", e)
        else:
            print("CSV validation passed.")

    return (1 if errors else 0), errors


if __name__ == "__main__":
    code, _ = validate(emit=True)
    sys.exit(code)

