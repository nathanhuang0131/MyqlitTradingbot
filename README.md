# MyGameRPG (pygame-ce v1)

A data-driven 2D top-down JRPG prototype with anime-drama tone.

## Requirements
- Python 3.11+
- pygame-ce
- pydantic

## Run
```bash
python -m game.main
```

## Controls
- Title: `N` new game, `L` load.
- Class select: `↑/↓` then `Enter`.
- Overworld: arrows move (1 tile = 1 round), `S` save, `R` relationship gift test.
- Battle/dialogue: `Space` continue.

## Features in v1
- Fixed map 25x18, tile size 32.
- Day/round system (5 rounds/day).
- Random battle on danger tiles (15% move chance).
- Turn-based battle (initiative, player-vs-monsters, drops, EXP/skill points).
- Recruitment of one companion (Lady Airi) + relationship progression.
- CSV-driven static game data in `game/data/csv`.
- JSON save/load in `game/data/saves`.

## Folder overview
- `game/main.py`: pygame scene manager and game loop.
- `game/core/`: state, save/load, deterministic RNG, data loader.
- `game/systems/`: battle, party, inventory, skills, equipment, crafting, story, relationships.
- `game/world/`: map, tiles, tile events.
- `game/ui/`: HUD, menu, battle log and dialogue panel.
- `game/tools/generate_assets.py`: creates placeholder PNG tiles/sprites.
- `game/tools/validate_csv.py`: validates CSV schema and simple types.
- `tests/`: formula tests.

## CSV authoring
1. Keep IDs unique in each file.
2. Ensure required columns in `validate_csv.py` remain present.
3. Run:
```bash
python -m game.tools.validate_csv
```
4. Test launch after edits:
```bash
python -m game.main
```

## Notes
- Artifacts are unique and non-craftable in v1, tracked via `artifact_owners` in save state.
- God Given special route scaffolding and special skill IDs are included.
