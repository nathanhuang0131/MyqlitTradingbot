from __future__ import annotations

import pygame

from game.core.data_loader import load_database
from game.core.rng import RNGService
from game.core.save_load import load_game, save_game
from game.core.state import CharacterState, GameState
from game.settings import DANGER_ENCOUNTER_RATE, FPS, GRID_HEIGHT, GRID_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE
from game.systems.battle.engine import run_basic_battle
from game.systems.party.manager import recruit
from game.systems.relationship.manager import apply_gift, duo_skill_unlocked
from game.systems.story.flags import initialize_route_flags
from game.ui.battle_ui import draw_battle
from game.ui.dialogue_ui import draw_dialogue
from game.ui.hud import draw_hud
from game.ui.menus import draw_centered_lines
from game.world.events import recruitable_companion, tile_event
from game.world.map_loader import starter_grid
from game.world.tiles import COLORS


CLASSES = ["Mage", "Healer", "Paladin", "Warrior", "Thief", "Hunter", "Random"]
SPECIALS = [
    "Supreme Fighter",
    "King of Diablo",
    "World of Magician",
    "Light of Paladin",
    "Grand Killer",
    "God Given",
]


def make_player(selection: str, rng: RNGService) -> CharacterState:
    chosen = selection
    route = "ordinary"
    if selection == "Random":
        if rng.chance(0.005):
            chosen = rng.choice(SPECIALS)
        else:
            chosen = rng.choice(CLASSES[:-1])
    if chosen in SPECIALS:
        route = "god_given" if chosen == "God Given" else "special"
    cls_id = chosen.lower().replace(" ", "_")
    player = CharacterState(id="player", name=chosen, class_id=cls_id)
    if chosen == "God Given":
        player.skills = {"gold_converter": 1, "mana_eater": 1, "special_killer": 1, "arcane_burst": 1}
    return player, route


def make_monster(name: str) -> CharacterState:
    return CharacterState(id=name.lower(), name=name, class_id="monster", hp=55, max_hp=55, mp=10, max_mp=10, atk=9, defense=4, mag=4, mdef=3, agi=7, luck=2)


def draw_overworld(screen, state, grid):
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            tile = grid[y][x]
            color = COLORS.get(tile, (0, 0, 0))
            pygame.draw.rect(screen, color, pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    px, py = state.position
    pygame.draw.rect(screen, (40, 60, 220), pygame.Rect(px * TILE_SIZE + 4, py * TILE_SIZE + 4, 24, 24))
    draw_hud(screen, state)


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("MyGameRPG v1")
    clock = pygame.time.Clock()
    rng = RNGService(2025)
    _db = load_database()

    scene = "title"
    class_idx = 0
    state: GameState | None = None
    grid = starter_grid()
    battle_log: list[str] = []
    dialogue_text = ""

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if scene == "title":
                    if event.key == pygame.K_n:
                        scene = "select"
                    elif event.key == pygame.K_l:
                        loaded = load_game()
                        if loaded:
                            state = loaded
                            scene = "overworld"
                elif scene == "select":
                    if event.key == pygame.K_UP:
                        class_idx = (class_idx - 1) % len(CLASSES)
                    if event.key == pygame.K_DOWN:
                        class_idx = (class_idx + 1) % len(CLASSES)
                    if event.key == pygame.K_RETURN:
                        player, route = make_player(CLASSES[class_idx], rng)
                        state = GameState(player=player, route_id=route)
                        initialize_route_flags(state)
                        scene = "overworld"
                elif scene == "overworld" and state:
                    dx, dy = 0, 0
                    if event.key == pygame.K_LEFT:
                        dx = -1
                    elif event.key == pygame.K_RIGHT:
                        dx = 1
                    elif event.key == pygame.K_UP:
                        dy = -1
                    elif event.key == pygame.K_DOWN:
                        dy = 1
                    elif event.key == pygame.K_s:
                        save_game(state)
                    elif event.key == pygame.K_r:
                        apply_gift(state, "lady_airi", affection=10, trust=8)
                    if dx or dy:
                        x, y = state.position
                        nx, ny = max(0, min(GRID_WIDTH - 1, x + dx)), max(0, min(GRID_HEIGHT - 1, y + dy))
                        state.position = (nx, ny)
                        state.consume_round()
                        tile = grid[ny][nx]
                        te = tile_event(state, tile)
                        if te:
                            dialogue_text = te
                            scene = "dialogue"
                        if tile == "danger" and rng.chance(DANGER_ENCOUNTER_RATE):
                            monsters = [make_monster("Goblin"), make_monster("Slime")]
                            result = run_basic_battle(state, monsters)
                            battle_log = result.log + [f"Victory: {result.victory} EXP+{result.exp_gained} G+{result.gold_gained}"]
                            if not state.flags.check("recruited_airi") and result.victory:
                                if recruit(state, recruitable_companion()):
                                    state.flags.set("recruited_airi", True)
                            scene = "battle"
                elif scene == "battle":
                    if event.key == pygame.K_SPACE:
                        scene = "overworld"
                elif scene == "dialogue":
                    if event.key == pygame.K_SPACE:
                        scene = "overworld"

        if scene == "title":
            screen.fill((15, 15, 28))
            draw_centered_lines(screen, ["MYGAME RPG", "N: New Game", "L: Load Game"])
        elif scene == "select":
            screen.fill((20, 20, 20))
            lines = ["Choose Class (Enter)"] + [f"{'>' if i == class_idx else ' '} {c}" for i, c in enumerate(CLASSES)]
            draw_centered_lines(screen, lines)
        elif scene == "overworld" and state:
            draw_overworld(screen, state, grid)
            if duo_skill_unlocked(state, "lady_airi"):
                draw_dialogue(screen, "Duo Skill Unlocked: Crescent Logic")
        elif scene == "battle":
            draw_battle(screen, battle_log + ["Press SPACE to continue"])
        elif scene == "dialogue":
            draw_overworld(screen, state, grid)
            draw_dialogue(screen, dialogue_text + " (SPACE)")

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
