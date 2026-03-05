# MyGameRPG

A data-driven 2D RPG prototype (pygame/pygame-ce) with CSV-backed story, dialogue, routes, gifts, and relationships.

## Requirements
- Python 3.11+
- pygame-ce
- pydantic
- pytest

## Quick Runbook
```bash
pip install pygame-ce pytest pydantic
python -m game.tools.fetch_assets        # optional: downloads, else creates placeholders
python -m game.tools.generate_skill_icons
python -m game.tools.validate_csv
python -m game.main
```

Debug keys in overworld:
- `F1`: toggle encounter debug overlay (tile id, danger flag, roll, trigger)
- `F2`: force encounter on next move

## Run (repo root)
```bash
python -m game.main
```

## Validate Story CSV
```bash
python -m game.tools.validate_csv
```

## Test
```bash
pytest -q -p no:cacheprovider
```

## Current Vertical Slice
- Fixed-screen overworld: `25x18` tiles, `32x32` tile size.
- Danger tile encounter rate: `15%` per move (deterministic via seeded RNG service).
- Chapter 1 flow is CSV-driven:
  - Town intro
  - Notice board
  - Meet/recruit Airi with dialogue choices affecting affection/trust
  - Ruins gate travel and encounter
  - Supreme Fighter cameo
  - Shrine scene
  - Chapter 1 complete state/flag
- Save/load JSON in `game/assets/data/saves`.
- Assets and attributions are in `game/assets/licenses/`:
  - `LPC_BASE_ASSETS.txt`
  - `LPC_GOBLIN.txt`

See `user-manual.md` for controls and authoring guidance.
