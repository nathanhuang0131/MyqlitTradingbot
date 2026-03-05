import pygame


def draw_battle(
    screen: pygame.Surface,
    lines: list[str],
    party_sprites: list[pygame.Surface] | None = None,
    enemy_sprites: list[pygame.Surface] | None = None,
    target_idx: int = 0,
    skill_entries: list[tuple[str, str, pygame.Surface | None]] | None = None,
    selected_skill_idx: int = 0,
) -> None:
    font = pygame.font.SysFont("consolas", 20)
    small = pygame.font.SysFont("consolas", 16)
    screen.fill((30, 20, 20))

    for i, sprite in enumerate(party_sprites or []):
        screen.blit(sprite, (40, 60 + i * 52))
    for i, sprite in enumerate(enemy_sprites or []):
        x = screen.get_width() - 76
        y = 60 + i * 52
        screen.blit(sprite, (x, y))
        if i == target_idx:
            pygame.draw.rect(screen, (255, 220, 90), pygame.Rect(x - 2, y - 2, 36, 36), 2)

    skills = skill_entries or []
    for i, (_, name, icon) in enumerate(skills[:6]):
        y = 60 + i * 36
        marker = ">" if i == selected_skill_idx else " "
        color = (235, 235, 235) if i == selected_skill_idx else (185, 185, 185)
        if icon:
            screen.blit(icon, (screen.get_width() // 2 - 30, y))
        screen.blit(small.render(f"{marker} {name}", True, color), (screen.get_width() // 2 + 8, y + 8))

    for i, line in enumerate(lines[-18:]):
        screen.blit(font.render(line, True, (230, 230, 230)), (16, 300 + 20 * i))
