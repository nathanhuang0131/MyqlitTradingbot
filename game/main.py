from __future__ import annotations

import pygame

from game.assets.asset_manager import AssetManager
from game.assets.core.data_loader import load_database
from game.assets.core.rng import RNGService
from game.assets.core.save_load import load_game, save_game
from game.assets.core.state import CharacterState, GameState
from game.settings import DANGER_ENCOUNTER_RATE, FPS, GRID_HEIGHT, GRID_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE
from game.systems.battle.engine import run_basic_battle
from game.systems.encounter import ENCOUNTER_TABLE, EncounterSystem
from game.systems.inventory.manager import use_item
from game.systems.party.manager import recruit
from game.systems.relationship.manager import load_bond_thresholds
from game.systems.story.dialogue_manager import DialogueManager
from game.systems.story.event_manager import EventManager, EventOutcome
from game.systems.story.flags import initialize_route_flags
from game.tools.generate_skill_icons import generate_skill_icons
from game.ui.battle_ui import draw_battle
from game.ui.dialogue_ui import draw_dialogue
from game.ui.hud import draw_hint_bar, draw_hud
from game.ui.inventory_ui import draw_inventory
from game.ui.menus import draw_centered_lines
from game.world.events import recruitable_companion
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
HINT_TEXT = "Move: WASD/Arrows | Interact: E | Inventory: I | Menu: ESC"


def _row_get(row, key: str, default=""):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def make_player(selection: str, rng: RNGService) -> tuple[CharacterState, str]:
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


def _monster_from_row(row: dict[str, str]) -> CharacterState:
    return CharacterState(
        id=str(_row_get(row, "id", "monster")).strip(),
        name=str(_row_get(row, "name", "Monster")).strip(),
        class_id="monster",
        hp=int(float(_row_get(row, "hp", 50) or 50)),
        max_hp=int(float(_row_get(row, "hp", 50) or 50)),
        mp=int(float(_row_get(row, "mp", 0) or 0)),
        max_mp=int(float(_row_get(row, "mp", 0) or 0)),
        atk=int(float(_row_get(row, "atk", 8) or 8)),
        defense=int(float(_row_get(row, "defense", 3) or 3)),
        mag=int(float(_row_get(row, "mag", 3) or 3)),
        mdef=int(float(_row_get(row, "mdef", 2) or 2)),
        agi=int(float(_row_get(row, "agi", 5) or 5)),
        luck=int(float(_row_get(row, "luck", 3) or 3)),
    )


def make_encounter(encounter_id: str, db: dict) -> list[CharacterState]:
    monster_ids = ENCOUNTER_TABLE.get(encounter_id, ENCOUNTER_TABLE["danger_default"])
    rows = {str(_row_get(row, "id", "")).strip(): row for row in db.get("monsters", [])}
    monsters: list[CharacterState] = []
    for mon_id in monster_ids:
        row = rows.get(mon_id)
        if row:
            monsters.append(_monster_from_row(row))
    if not monsters:
        fallback = next(iter(rows.values()), {"id": "goblin", "name": "Goblin"})
        monsters = [_monster_from_row(fallback)]
    return monsters


def _default_skill_by_class(db: dict) -> dict[str, str]:
    defaults: dict[str, str] = {}
    for row in db.get("skill_progression", []):
        class_id = (row.get("class_id") or "").strip()
        skill_id = (row.get("skill_id") or "").strip()
        if not class_id or not skill_id:
            continue
        if int(float(row.get("level") or 1)) == 1 and class_id not in defaults:
            defaults[class_id] = skill_id
    return defaults


def ensure_party_skills(state: GameState, db: dict) -> None:
    defaults = _default_skill_by_class(db)
    all_skills = {str(_row_get(row, "id", "")).strip() for row in db.get("skills", [])}
    fallback = "slash" if "slash" in all_skills else next(iter(all_skills), "")

    for actor in state.active_party:
        if actor.skills:
            continue
        skill_id = defaults.get(actor.class_id, fallback)
        if skill_id:
            actor.skills = {skill_id: 1}


def draw_overworld(screen: pygame.Surface, state: GameState, grid: list[list[str]], assets: AssetManager) -> None:
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            tile = grid[y][x]
            color = COLORS.get(tile, (0, 0, 0))
            pygame.draw.rect(screen, color, pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))

    # Airi town sprite before recruitment.
    if not state.flags.check("recruited_airi"):
        screen.blit(assets.character_sprite("airi"), (5 * TILE_SIZE, 3 * TILE_SIZE))

    px, py = state.position
    screen.blit(assets.character_sprite("player"), (px * TILE_SIZE, py * TILE_SIZE))
    draw_hud(screen, state)
    draw_hint_bar(screen, HINT_TEXT)


def draw_debug_overlay(screen: pygame.Surface, encounters: EncounterSystem, state: GameState) -> None:
    font = pygame.font.SysFont("consolas", 16)
    x, y = state.position
    roll = "-" if encounters.last_roll is None else f"{encounters.last_roll:.3f}"
    lines = [
        f"tile_id={encounters.last_tile_id or 'n/a'} pos=({x},{y})",
        f"is_danger={encounters.last_is_danger}",
        f"last_roll={roll}",
        f"encounter_triggered={encounters.last_triggered}",
        f"force_next={encounters.force_next}",
    ]
    panel = pygame.Rect(8, 32, 290, 96)
    pygame.draw.rect(screen, (12, 12, 12), panel)
    pygame.draw.rect(screen, (220, 220, 220), panel, 1)
    for i, line in enumerate(lines):
        screen.blit(font.render(line, True, (235, 235, 235)), (12, 36 + i * 18))


def apply_outcome(
    state: GameState,
    outcome: EventOutcome,
    dialogue_manager: DialogueManager,
    db: dict,
) -> tuple[str | None, list[CharacterState] | None, str | None]:
    scene_override: str | None = None
    monsters: list[CharacterState] | None = None
    popup: str | None = None

    if outcome.recruit_id == "lady_airi":
        if recruit(state, recruitable_companion()):
            state.flags.set("recruited_airi", True)

    if outcome.dialogue_start_id:
        dialogue_manager.start(outcome.dialogue_start_id)
        scene_override = "dialogue"

    if outcome.encounter_id:
        monsters = make_encounter(outcome.encounter_id, db)
        scene_override = "battle"

    if outcome.popup_text:
        popup = outcome.popup_text

    return scene_override, monsters, popup


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("MyGameRPG v1")
    clock = pygame.time.Clock()

    rng = RNGService(2025)
    db = load_database()
    load_bond_thresholds(db.get("bond_thresholds", []))
    generate_skill_icons()

    event_manager = EventManager(db.get("events", []))
    dialogue_manager = DialogueManager(db.get("dialogue", []))
    assets = AssetManager()
    encounters = EncounterSystem(chance=DANGER_ENCOUNTER_RATE)

    scene = "title"
    class_idx = 0
    state: GameState | None = None
    grid = starter_grid()
    battle_log: list[str] = []
    popup_text = ""
    popup_timer = 0

    pending_monsters: list[CharacterState] = []
    target_idx = 0
    battle_skill_idx = 0
    debug_overlay = False

    inventory_tab = 0
    inventory_idx = 0
    pause_idx = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type != pygame.KEYDOWN:
                continue

            if scene == "title":
                if event.key == pygame.K_n:
                    scene = "select"
                elif event.key == pygame.K_l:
                    loaded = load_game()
                    if loaded:
                        state = loaded
                        ensure_party_skills(state, db)
                        scene = "overworld"

            elif scene == "select":
                if event.key == pygame.K_UP:
                    class_idx = (class_idx - 1) % len(CLASSES)
                if event.key == pygame.K_DOWN:
                    class_idx = (class_idx + 1) % len(CLASSES)
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    player, route = make_player(CLASSES[class_idx], rng)
                    state = GameState(player=player, route_id=route)
                    initialize_route_flags(state)
                    ensure_party_skills(state, db)
                    dialogue_manager.start("D_CH1_001")
                    scene = "dialogue"

            elif scene == "overworld" and state:
                dx, dy = 0, 0
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    dx = -1
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    dx = 1
                elif event.key in (pygame.K_UP, pygame.K_w):
                    dy = -1
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    dy = 1
                elif event.key == pygame.K_F1:
                    debug_overlay = not debug_overlay
                elif event.key == pygame.K_F2:
                    encounters.force_next_encounter()
                    popup_text = "Encounter forced for next move"
                    popup_timer = 90
                elif event.key == pygame.K_i:
                    inventory_tab = 0
                    inventory_idx = 0
                    scene = "inventory"
                elif event.key == pygame.K_ESCAPE:
                    pause_idx = 0
                    scene = "pause"
                elif event.key == pygame.K_l:
                    loaded = load_game()
                    if loaded:
                        state = loaded
                        ensure_party_skills(state, db)
                        popup_text = "Game Loaded"
                        popup_timer = 90
                elif event.key == pygame.K_e or event.key == pygame.K_SPACE:
                    outcome = event_manager.process(state, "on_interact")
                    if outcome:
                        scene_override, monsters, popup = apply_outcome(state, outcome, dialogue_manager, db)
                        ensure_party_skills(state, db)
                        if monsters:
                            pending_monsters = monsters
                            target_idx = 0
                            battle_skill_idx = 0
                        if popup:
                            popup_text = popup
                            popup_timer = 160
                        if scene_override:
                            scene = scene_override

                if dx or dy:
                    x, y = state.position
                    nx, ny = max(0, min(GRID_WIDTH - 1, x + dx)), max(0, min(GRID_HEIGHT - 1, y + dy))
                    if (nx, ny) != (x, y):
                        state.position = (nx, ny)
                        state.consume_round()

                        outcome = event_manager.process(state, "on_enter")
                        if outcome:
                            scene_override, monsters, popup = apply_outcome(state, outcome, dialogue_manager, db)
                            ensure_party_skills(state, db)
                            if monsters:
                                pending_monsters = monsters
                                target_idx = 0
                                battle_skill_idx = 0
                            if popup:
                                popup_text = popup
                                popup_timer = 160
                            if scene_override:
                                scene = scene_override
                        else:
                            tile = grid[ny][nx]
                            if encounters.roll_for_tile(tile, rng):
                                pending_monsters = make_encounter("danger_default", db)
                                target_idx = 0
                                battle_skill_idx = 0
                                scene = "battle"

            elif scene == "inventory" and state:
                entries = [
                    *state.inventory.items.keys()
                ] if inventory_tab == 0 else [
                    "equip"
                ] if inventory_tab == 1 else [
                    skill for actor in state.active_party for skill in actor.skills.keys()
                ]

                if event.key == pygame.K_ESCAPE:
                    scene = "overworld"
                elif event.key in (pygame.K_TAB, pygame.K_RIGHT):
                    inventory_tab = (inventory_tab + 1) % 3
                    inventory_idx = 0
                elif event.key == pygame.K_LEFT:
                    inventory_tab = (inventory_tab - 1) % 3
                    inventory_idx = 0
                elif event.key == pygame.K_UP:
                    inventory_idx = (inventory_idx - 1) % max(1, len(entries))
                elif event.key == pygame.K_DOWN:
                    inventory_idx = (inventory_idx + 1) % max(1, len(entries))
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if inventory_tab == 0 and entries:
                        item_id = entries[inventory_idx]
                        if use_item(state, item_id):
                            popup_text = f"Used {item_id}"
                            popup_timer = 80

            elif scene == "pause" and state:
                options = ["Resume", "Save", "Load", "Title"]
                if event.key == pygame.K_ESCAPE:
                    scene = "overworld"
                elif event.key == pygame.K_UP:
                    pause_idx = (pause_idx - 1) % len(options)
                elif event.key == pygame.K_DOWN:
                    pause_idx = (pause_idx + 1) % len(options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    choice = options[pause_idx]
                    if choice == "Resume":
                        scene = "overworld"
                    elif choice == "Save":
                        save_game(state)
                        popup_text = "Game Saved"
                        popup_timer = 90
                        scene = "overworld"
                    elif choice == "Load":
                        loaded = load_game()
                        if loaded:
                            state = loaded
                            ensure_party_skills(state, db)
                            popup_text = "Game Loaded"
                            popup_timer = 90
                        scene = "overworld"
                    elif choice == "Title":
                        scene = "title"

            elif scene == "battle" and state:
                if not pending_monsters:
                    scene = "overworld"
                    continue

                player_skill_ids = list(state.player.skills.keys()) or ["slash"]
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    target_idx = (target_idx - 1) % len(pending_monsters)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    target_idx = (target_idx + 1) % len(pending_monsters)
                elif event.key == pygame.K_UP:
                    battle_skill_idx = (battle_skill_idx - 1) % len(player_skill_ids)
                elif event.key == pygame.K_DOWN:
                    battle_skill_idx = (battle_skill_idx + 1) % len(player_skill_ids)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    focus = target_idx
                    chosen_skill = player_skill_ids[battle_skill_idx]

                    def selector(_actor: CharacterState, candidates: list[CharacterState], _is_player: bool) -> int:
                        if not candidates:
                            return 0
                        return max(0, min(focus, len(candidates) - 1))

                    result = run_basic_battle(
                        state,
                        pending_monsters,
                        target_selector=selector,
                        skill_rows=[{k: _row_get(row, k, "") for k in ("id", "name", "skill_type", "power", "mp_cost", "status_effect")} for row in db.get("skills", [])],
                        player_skill_id=chosen_skill,
                    )
                    battle_log = result.log + [f"Victory: {result.victory} EXP+{result.exp_gained} G+{result.gold_gained}"]
                    pending_monsters = []
                    state.flags.set("last_battle_won", result.victory)
                    scene = "battle_result"

            elif scene == "battle_result":
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    scene = "overworld"

            elif scene == "dialogue" and state:
                choices = dialogue_manager.current_choices(state)
                if choices:
                    if event.key == pygame.K_UP:
                        target_idx = (target_idx - 1) % len(choices)
                    elif event.key == pygame.K_DOWN:
                        target_idx = (target_idx + 1) % len(choices)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        dialogue_manager.choose(state, choices[target_idx].node_id)
                        target_idx = 0
                        dialogue_manager.advance(state)
                        if not dialogue_manager.in_dialogue:
                            scene = "overworld"
                else:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        dialogue_manager.advance(state)
                        if not dialogue_manager.in_dialogue:
                            scene = "overworld"

        if scene == "title":
            screen.fill((15, 15, 28))
            draw_centered_lines(screen, ["MYGAME RPG", "N: New Game", "L: Load Game"])

        elif scene == "select":
            screen.fill((20, 20, 20))
            lines = ["Choose Class (Enter)"] + [f"{'>' if i == class_idx else ' '} {c}" for i, c in enumerate(CLASSES)]
            draw_centered_lines(screen, lines)

        elif scene == "overworld" and state:
            draw_overworld(screen, state, grid, assets)
            if debug_overlay:
                draw_debug_overlay(screen, encounters, state)

        elif scene == "inventory" and state:
            draw_inventory(screen, state, db, inventory_tab, inventory_idx, assets)

        elif scene == "pause":
            screen.fill((18, 18, 24))
            options = ["Resume", "Save", "Load", "Title"]
            lines = ["Pause"] + [f"{'>' if i == pause_idx else ' '} {o}" for i, o in enumerate(options)]
            draw_centered_lines(screen, lines)

        elif scene == "battle" and state:
            skill_map = {
                str(_row_get(row, "id", "")): {
                    "id": _row_get(row, "id", ""),
                    "name": _row_get(row, "name", ""),
                }
                for row in db.get("skills", [])
            }
            player_skill_ids = list(state.player.skills.keys()) or ["slash"]
            skill_entries = []
            for sid in player_skill_ids:
                row = skill_map.get(sid, {})
                skill_entries.append((sid, str(row.get("name") or sid), assets.skill_icon(sid)))

            lines = [
                "Battle: UP/DOWN skill, LEFT/RIGHT target, ENTER/SPACE confirm",
            ] + [f"[{i}] {m.name} HP {m.hp}" for i, m in enumerate(pending_monsters)]

            party_sprites = [assets.character_sprite("airi" if a.id == "lady_airi" else "player") for a in state.active_party]
            enemy_sprites = [assets.enemy_sprite((m.id or "goblin").lower()) for m in pending_monsters]
            draw_battle(
                screen,
                lines,
                party_sprites=party_sprites,
                enemy_sprites=enemy_sprites,
                target_idx=target_idx,
                skill_entries=skill_entries,
                selected_skill_idx=battle_skill_idx,
            )

        elif scene == "battle_result":
            draw_battle(screen, battle_log + ["Press SPACE to continue"])

        elif scene == "dialogue" and state:
            draw_overworld(screen, state, grid, assets)
            line = dialogue_manager.current_line()
            if line:
                choices = dialogue_manager.current_choices(state)
                labels = [choice.label for choice in choices]
                draw_dialogue(screen, line.text, speaker=line.speaker, choices=labels, selected_choice=target_idx)

        if popup_timer > 0:
            popup_timer -= 1
            draw_dialogue(screen, popup_text, speaker="System")

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
