from pathlib import Path

import pytest

from game.assets.asset_manager import AssetManager


def test_missing_sprite_generates_placeholder(tmp_path: Path):
    pygame = pytest.importorskip("pygame")
    pygame.init()
    try:
        manager = AssetManager(asset_root=tmp_path)
        sprite_path = tmp_path / "sprites" / "characters" / "player.png"

        surface = manager.load_image_or_placeholder(sprite_path, size=(32, 32), color=(12, 34, 56))

        assert surface.get_size() == (32, 32)
        assert sprite_path.exists()
    finally:
        pygame.quit()
