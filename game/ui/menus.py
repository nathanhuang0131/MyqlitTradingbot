import pygame


def draw_centered_lines(screen: pygame.Surface, lines: list[str]) -> None:
    font = pygame.font.SysFont("arial", 24)
    y = 150
    for line in lines:
        surf = font.render(line, True, (255, 255, 255))
        rect = surf.get_rect(center=(screen.get_width() // 2, y))
        screen.blit(surf, rect)
        y += 40
