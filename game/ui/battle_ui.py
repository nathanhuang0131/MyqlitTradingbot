import pygame


def draw_battle(screen: pygame.Surface, lines: list[str]) -> None:
    font = pygame.font.SysFont("consolas", 20)
    screen.fill((30, 20, 20))
    for i, line in enumerate(lines[-18:]):
        screen.blit(font.render(line, True, (230, 230, 230)), (16, 16 + 24 * i))
