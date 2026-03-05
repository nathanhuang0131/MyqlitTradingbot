# Overworld Encounters, Sprites, Inputs, and Skill Icons Design

**Date:** 2026-03-05

## Scope
Implement end-to-end goblin encounters, input key wiring, inventory and pause menus, sprite loading/rendering with offline-safe fallbacks, and per-skill icon generation/loading.

## Architecture
- Add modular systems for encounter rules and asset fallback loading.
- Keep story/dialogue text fully CSV-driven; no hardcoded narrative text in code.
- Keep battle engine deterministic and data-driven by reading skill and monster metadata from CSV.
- Add tool scripts for optional asset download and guaranteed icon/sprite generation when network is unavailable.

## Components
1. `game/systems/encounter.py`
- Danger tile classification
- Encounter roll state (`last_roll`, `is_danger`, `triggered`)
- F1/F2 debug support hooks

2. `game/assets/asset_manager.py`
- Load sprites/icons by path
- Auto-generate and cache placeholders/default icon when missing
- Return pygame surfaces sized for 32x32 tiles

3. `game/tools/fetch_assets.py`
- Attempt LPC zip/goblin downloads
- Extract/select character sprites where possible
- Fallback to generated `player.png`, `airi.png`, `goblin.png`
- Write attribution text files under `game/assets/licenses/`

4. `game/tools/generate_skill_icons.py`
- Read `skills.csv`
- Generate 32x32 icon PNG for each skill (`assets/sprites/skills/{skill_id}.png`)
- PIL-first, pygame fallback, default icon generation

5. UI additions
- Hint bar in overworld
- Inventory UI module with tabs: Items / Equipment / Skills
- Pause menu panel
- Battle UI sprite + skill icon rendering

6. Data and validation
- Ensure goblin spawnable encounter path
- Ensure player and Airi have at least one LV1 skill fallback
- CSV validator cross-check:
  - events/encounters reference existing monsters (by encounter mapping)
  - character/party skills reference existing skills

## Testing Strategy
- Encounter logic tests with seeded RNG and forced encounter toggle.
- Asset loader fallback tests for missing sprites.
- Skill icon generation test to assert icon file per skill id.
- CSV validator tests for missing monster/skill references.

## Acceptance
- Move on danger tile triggers 15% encounters and F2 force mode works.
- E/SPACE interacts/confirms; I opens inventory; ESC opens/closes pause/back.
- Player/Airi/Goblin sprites render in overworld/battle.
- Skill icons generated and shown in battle and inventory skills tab.
- Offline execution remains stable via placeholders.
