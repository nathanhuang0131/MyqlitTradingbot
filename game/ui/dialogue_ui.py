import pygame


def draw_dialogue(screen: pygame.Surface, text: str) -> None:
    font = pygame.font.SysFont("arial", 20)
    panel = pygame.Rect(40, screen.get_height() - 150, screen.get_width() - 80, 110)
    pygame.draw.rect(screen, (20, 20, 60), panel)
    pygame.draw.rect(screen, (200, 200, 255), panel, 2)
    screen.blit(font.render(text[:90], True, (255, 255, 255)), (panel.x + 10, panel.y + 40))
