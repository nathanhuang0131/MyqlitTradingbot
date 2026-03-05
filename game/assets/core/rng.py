import random
from dataclasses import dataclass


@dataclass
class RNGService:
    seed: int = 777

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)

    def chance(self, pct: float) -> bool:
        return self._random.random() < pct

    def roll(self) -> float:
        return self._random.random()

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def choice(self, items):
        return self._random.choice(items)
