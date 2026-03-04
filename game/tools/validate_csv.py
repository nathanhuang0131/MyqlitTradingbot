from __future__ import annotations

import csv
import sys
from pathlib import Path

from game.settings import CSV_DIR

REQUIRED = {
    "classes.csv": ["id", "name", "hp", "mp", "atk", "defense", "mag", "mdef", "agi", "luck"],
    "characters.csv": ["id", "name", "class_id", "faction", "role", "is_special"],
    "skills.csv": ["id", "name", "skill_type", "power", "mp_cost", "hit_rate", "status_effect"],
    "monsters.csv": ["id", "name", "hp", "mp", "atk", "defense", "mag", "mdef", "agi", "luck", "exp", "gold", "drops"],
    "artifacts.csv": ["id", "name", "owner_hint", "unique", "craftable"],
}

NUMERIC = {
    "classes.csv": ["hp", "mp", "atk", "defense", "mag", "mdef", "agi", "luck"],
    "skills.csv": ["power", "mp_cost", "hit_rate"],
    "monsters.csv": ["hp", "exp", "gold"],
}


def validate() -> int:
    errors: list[str] = []
    for file, cols in REQUIRED.items():
        path = CSV_DIR / file
        if not path.exists():
            errors.append(f"Missing file: {file}")
            continue
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = [c for c in cols if c not in (reader.fieldnames or [])]
            if missing:
                errors.append(f"{file} missing columns: {missing}")
            for i, row in enumerate(reader, 2):
                for col in NUMERIC.get(file, []):
                    try:
                        float(row[col])
                    except Exception:
                        errors.append(f"{file}:{i} invalid numeric {col}={row.get(col)}")
    if errors:
        print("CSV validation failed:")
        for e in errors:
            print(" -", e)
        return 1
    print("CSV validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
