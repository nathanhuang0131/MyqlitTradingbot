from __future__ import annotations

import pygame

from game.assets.asset_manager import AssetManager

TABS = ["Items", "Equipment", "Skills"]


def draw_inventory(
    screen: pygame.Surface,
    state,
    db: dict,
    tab_index: int,
    selected_index: int,
    asset_manager: AssetManager,
) -> None:
    screen.fill((20, 24, 34))
    font = pygame.font.SysFont("consolas", 20)
    small = pygame.font.SysFont("consolas", 16)

    title = font.render("Inventory", True, (245, 245, 245))
    screen.blit(title, (18, 12))

    x = 18
    for i, tab in enumerate(TABS):
        color = (255, 225, 120) if i == tab_index else (180, 180, 180)
        screen.blit(small.render(f"[{tab}]", True, color), (x, 44))
        x += 110

    items = _tab_entries(state, db, tab_index)
    if not items:
        screen.blit(small.render("No entries", True, (160, 160, 160)), (20, 82))
    for i, entry in enumerate(items[:14]):
        marker = ">" if i == selected_index else " "
        color = (220, 255, 220) if i == selected_index else (220, 220, 220)
        text = f"{marker} {entry}"
        screen.blit(small.render(text, True, color), (20, 82 + i * 22))

    if tab_index == 2:
        _draw_skill_icons(screen, state, asset_manager)

    footer = "UP/DOWN: Select | ENTER/SPACE: Confirm | ESC: Back | LEFT/RIGHT/TAB: Change section"
    screen.blit(small.render(footer, True, (190, 190, 220)), (20, screen.get_height() - 26))


def _tab_entries(state, db: dict, tab_index: int) -> list[str]:
    if tab_index == 0:
        item_rows = {row["id"]: row for row in db.get("items", [])}
        lines = []
        for item_id, qty in sorted(state.inventory.items.items()):
            row = item_rows.get(item_id, {})
            name = row.get("name", item_id)
            desc = row.get("effect", "")
            lines.append(f"{name} x{qty} - {desc}")
        return lines
    if tab_index == 1:
        return ["Equipment not implemented yet"]

    skills: list[str] = []
    for actor in state.active_party:
        for skill_id, lvl in actor.skills.items():
            skills.append(f"{actor.name}: {skill_id} Lv{lvl}")
    return skills


def _draw_skill_icons(screen: pygame.Surface, state, asset_manager: AssetManager) -> None:
    x = screen.get_width() - 240
    y = 90
    seen: set[str] = set()
    for actor in state.active_party:
        for skill_id in actor.skills.keys():
            if skill_id in seen:
                continue
            seen.add(skill_id)
            icon = asset_manager.skill_icon(skill_id)
            screen.blit(icon, (x, y))
            y += 38
            if y > screen.get_height() - 60:
                y = 90
                x += 38
