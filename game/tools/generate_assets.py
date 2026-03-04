from pathlib import Path

import pygame

from game.settings import ASSET_DIR, TILE_SIZE


def save_square(path: Path, color: tuple[int, int, int], size: int = TILE_SIZE) -> None:
    surf = pygame.Surface((size, size))
    surf.fill(color)
    pygame.image.save(surf, str(path))


def main() -> None:
    pygame.init()
    (ASSET_DIR / "tiles").mkdir(parents=True, exist_ok=True)
    (ASSET_DIR / "sprites").mkdir(parents=True, exist_ok=True)
    colors = {
        "grass": (40, 150, 70),
        "danger": (110, 70, 50),
        "town": (220, 200, 60),
        "dungeon": (80, 80, 95),
        "shrine": (180, 170, 255),
        "kings_road": (130, 130, 130),
        "player": (40, 60, 220),
    }
    for key, color in colors.items():
        target = "sprites" if key == "player" else "tiles"
        save_square(ASSET_DIR / target / f"{key}.png", color)
    pygame.quit()


if __name__ == "__main__":
    main()
