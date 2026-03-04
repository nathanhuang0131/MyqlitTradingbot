import pygame


def draw_hud(screen: pygame.Surface, state) -> None:
    font = pygame.font.SysFont("arial", 18)
    text = f"Day {state.day} | Rounds {state.rounds_remaining_today} | Gold {state.inventory.gold}"
    screen.blit(font.render(text, True, (255, 255, 255)), (8, 4))
