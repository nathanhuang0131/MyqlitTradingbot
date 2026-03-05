import pygame


def draw_hud(screen: pygame.Surface, state) -> None:
    font = pygame.font.SysFont("arial", 18)
    text = f"Day {state.day} | Rounds {state.rounds_remaining_today} | Gold {state.inventory.gold}"
    screen.blit(font.render(text, True, (255, 255, 255)), (8, 4))


def draw_hint_bar(screen: pygame.Surface, text: str) -> None:
    font = pygame.font.SysFont("consolas", 16)
    h = 26
    rect = pygame.Rect(0, screen.get_height() - h, screen.get_width(), h)
    pygame.draw.rect(screen, (16, 16, 28), rect)
    pygame.draw.line(screen, (90, 90, 120), (0, rect.y), (screen.get_width(), rect.y), 1)
    screen.blit(font.render(text, True, (220, 220, 240)), (8, rect.y + 5))
