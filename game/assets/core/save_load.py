import json
from pathlib import Path

from game.core.state import GameState
from game.settings import SAVE_DIR


def save_game(state: GameState, filename: str = "slot1.json") -> Path:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    path = SAVE_DIR / filename
    path.write_text(json.dumps(state.model_dump(), indent=2), encoding="utf-8")
    return path


def load_game(filename: str = "slot1.json") -> GameState | None:
    path = SAVE_DIR / filename
    if not path.exists():
        return None
    return GameState.model_validate(json.loads(path.read_text(encoding="utf-8")))
