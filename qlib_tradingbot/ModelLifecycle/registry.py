from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelCard:
    model_id: str
    strategy_id: str
    metrics: dict[str, float] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    artifact_path: str = ""
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ModelRegistry:
    def __init__(self, root_dir: str | Path = "Data/model_registry") -> None:
        self.root = Path(root_dir)
        self.cards_dir = self.root / "model_cards"
        self.production_path = self.root / "production_model.json"
        self.cards_dir.mkdir(parents=True, exist_ok=True)

    def card_path(self, model_id: str) -> Path:
        return self.cards_dir / f"{model_id}.json"

    def register(self, card: ModelCard) -> Path:
        path = self.card_path(card.model_id)
        path.write_text(json.dumps(asdict(card), indent=2), encoding="utf-8")
        return path

    def get(self, model_id: str) -> ModelCard | None:
        path = self.card_path(model_id)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ModelCard(**payload)

    def list(self, strategy_id: str | None = None) -> list[ModelCard]:
        cards: list[ModelCard] = []
        for path in sorted(self.cards_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            card = ModelCard(**payload)
            if strategy_id and card.strategy_id != strategy_id:
                continue
            cards.append(card)
        return cards

    def set_production(self, model_id: str) -> Path:
        if self.get(model_id) is None:
            raise ValueError(f"Unknown model_id: {model_id}")
        self.production_path.write_text(json.dumps({"model_id": model_id}, indent=2), encoding="utf-8")
        return self.production_path

    def get_production(self) -> str | None:
        if not self.production_path.is_file():
            return None
        payload = json.loads(self.production_path.read_text(encoding="utf-8"))
        return str(payload.get("model_id") or "") or None
