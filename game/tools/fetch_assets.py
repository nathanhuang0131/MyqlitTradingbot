from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

from game.tools.generate_skill_icons import _write_solid_png
from game.settings import ASSET_DIR

LPC_BASE_URL = "https://opengameart.org/content/liberated-pixel-cup-lpc-base-assets-sprites-map-tiles"
LPC_GOBLIN_URL = "https://opengameart.org/content/lpc-goblin"


def _download_bytes(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read()
    except Exception:
        return None


def _extract_first_png_from_zip(zip_bytes: bytes) -> bytes | None:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            png_names = [n for n in zf.namelist() if n.lower().endswith(".png")]
            if not png_names:
                return None
            return zf.read(png_names[0])
    except Exception:
        return None


def _write_if_downloaded(target: Path, data: bytes | None) -> bool:
    if not data:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_bytes(data)
        return True
    except Exception:
        return False


def _write_attributions(licenses_dir: Path) -> None:
    licenses_dir.mkdir(parents=True, exist_ok=True)
    (licenses_dir / "LPC_BASE_ASSETS.txt").write_text(
        "Source: https://opengameart.org/content/liberated-pixel-cup-lpc-base-assets-sprites-map-tiles\n"
        "License/Attribution: See original OpenGameArt page for current license and attribution requirements.\n",
        encoding="utf-8",
    )
    (licenses_dir / "LPC_GOBLIN.txt").write_text(
        "Source: https://opengameart.org/content/lpc-goblin\n"
        "License/Attribution: See original OpenGameArt page for current license and attribution requirements.\n",
        encoding="utf-8",
    )


def fetch_assets(asset_root: Path = ASSET_DIR) -> dict[str, bool]:
    chars_dir = asset_root / "sprites" / "characters"
    enemies_dir = asset_root / "sprites" / "enemies"
    licenses_dir = asset_root / "licenses"
    chars_dir.mkdir(parents=True, exist_ok=True)
    enemies_dir.mkdir(parents=True, exist_ok=True)

    player_path = chars_dir / "player.png"
    airi_path = chars_dir / "airi.png"
    goblin_path = enemies_dir / "goblin.png"

    results = {"player": False, "airi": False, "goblin": False}

    # OpenGameArt pages are not guaranteed direct-file links; try best effort and fallback.
    base_bytes = _download_bytes(LPC_BASE_URL)
    extracted = _extract_first_png_from_zip(base_bytes) if base_bytes else None
    results["player"] = _write_if_downloaded(player_path, extracted)
    results["airi"] = _write_if_downloaded(airi_path, extracted)

    goblin_bytes = _download_bytes(LPC_GOBLIN_URL)
    results["goblin"] = _write_if_downloaded(goblin_path, goblin_bytes)

    if not player_path.exists():
        _write_solid_png(player_path, (60, 110, 220))
    if not airi_path.exists():
        _write_solid_png(airi_path, (210, 120, 180))
    if not goblin_path.exists():
        _write_solid_png(goblin_path, (50, 160, 70))

    _write_attributions(licenses_dir)
    return results


if __name__ == "__main__":
    outcome = fetch_assets()
    print(
        "Assets ready:"
        f" player={'downloaded' if outcome['player'] else 'placeholder'},"
        f" airi={'downloaded' if outcome['airi'] else 'placeholder'},"
        f" goblin={'downloaded' if outcome['goblin'] else 'placeholder'}"
    )

