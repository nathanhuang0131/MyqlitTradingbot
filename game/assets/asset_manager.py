from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from game.settings import ASSET_DIR

if TYPE_CHECKING:
    import pygame


class AssetManager:
    def __init__(self, asset_root: Path | None = None) -> None:
        self.asset_root = asset_root or ASSET_DIR
        self._cache: dict[str, "pygame.Surface"] = {}

    def load_image_or_placeholder(
        self,
        path: Path,
        size: tuple[int, int] = (32, 32),
        color: tuple[int, int, int] = (120, 120, 120),
        label: str = "",
    ) -> "pygame.Surface":
        import pygame

        key = str(path.resolve()) if path.is_absolute() else str(path)
        if key in self._cache:
            return self._cache[key]

        path.parent.mkdir(parents=True, exist_ok=True)
        surface: "pygame.Surface"
        if path.exists():
            try:
                surface = pygame.image.load(str(path))
            except Exception:
                surface = self._placeholder(size, color, label)
                pygame.image.save(surface, str(path))
        else:
            surface = self._placeholder(size, color, label)
            pygame.image.save(surface, str(path))

        if surface.get_size() != size:
            surface = pygame.transform.scale(surface, size)
        self._cache[key] = surface
        return surface

    def character_sprite(self, sprite_id: str) -> "pygame.Surface":
        filename = f"{sprite_id}.png"
        path = self.asset_root / "sprites" / "characters" / filename
        default_color = (70, 120, 220) if sprite_id == "player" else (220, 120, 190)
        return self.load_image_or_placeholder(path, color=default_color, label=sprite_id[:2].upper())

    def enemy_sprite(self, sprite_id: str) -> "pygame.Surface":
        filename = f"{sprite_id}.png"
        path = self.asset_root / "sprites" / "enemies" / filename
        return self.load_image_or_placeholder(path, color=(40, 170, 70), label=sprite_id[:2].upper())

    def skill_icon(self, skill_id: str) -> "pygame.Surface":
        path = self.asset_root / "sprites" / "skills" / f"{skill_id}.png"
        if path.exists():
            return self.load_image_or_placeholder(path, color=(70, 70, 70), label=skill_id[:2].upper())
        default_path = self.asset_root / "sprites" / "skills" / "_default.png"
        return self.load_image_or_placeholder(default_path, color=(80, 80, 120), label="?")

    def _placeholder(self, size: tuple[int, int], color: tuple[int, int, int], label: str) -> "pygame.Surface":
        import pygame

        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((*color, 255))
        pygame.draw.rect(surf, (20, 20, 20), surf.get_rect(), 2)
        if label and pygame.font.get_init():
            font = pygame.font.SysFont("consolas", 12)
            text = font.render(label[:3], True, (245, 245, 245))
            rect = text.get_rect(center=(size[0] // 2, size[1] // 2))
            surf.blit(text, rect)
        return surf
