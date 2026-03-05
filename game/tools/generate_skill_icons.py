from __future__ import annotations

import csv
import struct
import zlib
from pathlib import Path

from game.settings import ASSET_DIR, CSV_DIR

TYPE_COLORS: dict[str, tuple[int, int, int]] = {
    "physical": (175, 65, 60),
    "magic": (55, 95, 180),
    "heal": (60, 150, 95),
    "status": (130, 95, 170),
    "special": (145, 120, 50),
    "passive": (110, 110, 110),
}


def _abbr(name: str) -> str:
    words = [w for w in name.replace("-", " ").split() if w]
    if len(words) >= 2:
        return (words[0][:1] + words[1][:1]).upper()
    if words:
        return words[0][:3].upper()
    return "SKL"


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def _write_solid_png(path: Path, color: tuple[int, int, int], width: int = 32, height: int = 32) -> None:
    row = bytes([color[0], color[1], color[2]]) * width
    raw = b"".join(b"\x00" + row for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", zlib.compress(raw, level=9))
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _write_with_pillow(path: Path, skill_name: str, color: tuple[int, int, int]) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False

    image = Image.new("RGB", (32, 32), color=color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 31, 31), outline=(20, 20, 20), width=1)
    text = _abbr(skill_name)
    font = ImageFont.load_default()
    draw.text((7, 10), text, fill=(245, 245, 245), font=font)
    image.save(path)
    return True


def _write_with_pygame(path: Path, skill_name: str, color: tuple[int, int, int]) -> bool:
    try:
        import pygame
    except Exception:
        return False

    pygame.init()
    try:
        if not pygame.font.get_init():
            pygame.font.init()
        surf = pygame.Surface((32, 32))
        surf.fill(color)
        pygame.draw.rect(surf, (20, 20, 20), surf.get_rect(), 1)
        font = pygame.font.SysFont("consolas", 12)
        text = font.render(_abbr(skill_name), True, (245, 245, 245))
        surf.blit(text, text.get_rect(center=(16, 16)))
        pygame.image.save(surf, str(path))
    finally:
        pygame.quit()
    return True


def _write_icon(path: Path, skill_name: str, color: tuple[int, int, int]) -> None:
    if _write_with_pillow(path, skill_name, color):
        return
    if _write_with_pygame(path, skill_name, color):
        return
    _write_solid_png(path, color)


def generate_skill_icons(
    skills_csv: Path = CSV_DIR / "skills.csv",
    output_dir: Path = ASSET_DIR / "sprites" / "skills",
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    with skills_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            skill_id = (row.get("id") or "").strip()
            if not skill_id:
                continue
            name = (row.get("name") or skill_id).strip()
            skill_type = (row.get("skill_type") or "").strip().lower()
            color = TYPE_COLORS.get(skill_type, (90, 90, 120))
            icon_path = output_dir / f"{skill_id}.png"
            _write_icon(icon_path, name, color)
            generated.append(icon_path)

    _write_icon(output_dir / "_default.png", "?", (80, 80, 120))
    return generated


if __name__ == "__main__":
    icons = generate_skill_icons()
    print(f"Generated {len(icons)} skill icons at {ASSET_DIR / 'sprites' / 'skills'}")

