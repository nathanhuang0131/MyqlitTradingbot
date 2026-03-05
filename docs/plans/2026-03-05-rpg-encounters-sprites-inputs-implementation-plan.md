# RPG Encounters/Sprites/Inputs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver reliable goblin encounters, keybindings/menu flows, sprite/icon asset pipeline with offline fallbacks, and verified battle/inventory integration.

**Architecture:** Extend existing game loop and battle systems with modular encounter and asset loaders, add dedicated inventory UI and icon generator tools, and validate data references with focused tests.

**Tech Stack:** Python 3.11+, pygame-ce, pytest, pydantic, optional Pillow.

---

### Task 1: Add failing tests for encounter, sprite fallback, skill icon generation

**Files:**
- Create: `game/tests/test_asset_fallbacks.py`
- Create: `game/tests/test_skill_icon_generation.py`
- Modify: `game/tests/test_encounters.py`

Steps:
1. Add tests for danger tile encounter roll metadata + forced encounter next move.
2. Add tests for missing sprite path returning generated placeholder surface.
3. Add tests that icon generator emits one PNG per skill id.

### Task 2: Implement encounter module and debug support

**Files:**
- Create: `game/systems/encounter.py`
- Modify: `game/main.py`

Steps:
1. Implement danger tile check + roll result object.
2. Wire F1 overlay and F2 force-next-encounter.
3. Integrate move-based encounter check into overworld movement.

### Task 3: Implement asset manager and sprite rendering

**Files:**
- Create: `game/assets/asset_manager.py`
- Modify: `game/main.py`
- Modify: `game/ui/battle_ui.py`

Steps:
1. Build image loader with placeholder/default icon generation.
2. Replace rectangle rendering with player/Airi/goblin sprites.
3. Render party left, enemies right in battle scene.

### Task 4: Add asset fetch tool and license files

**Files:**
- Create: `game/tools/fetch_assets.py`
- Create: `game/assets/licenses/LPC_BASE_ASSETS.txt`
- Create: `game/assets/licenses/LPC_GOBLIN.txt`

Steps:
1. Attempt downloads and extraction.
2. Fallback-generate required sprites if download fails.
3. Ensure license text references source URLs and attribution.

### Task 5: Add skill icon generator and UI loading

**Files:**
- Create: `game/tools/generate_skill_icons.py`
- Modify: `game/ui/battle_ui.py`
- Create: `game/ui/inventory_ui.py`
- Modify: `game/main.py`

Steps:
1. Generate icons for all skills with PIL or pygame fallback.
2. Load/render skill icons in battle and inventory skills tab.
3. Use default icon when missing.

### Task 6: Inventory/pause key wiring and controls

**Files:**
- Modify: `game/main.py`
- Modify: `game/ui/menus.py`

Steps:
1. Wire movement with arrows+WASD.
2. Wire Interact E and SPACE confirm behavior.
3. Wire inventory key I, pause key ESC, menu navigation controls.
4. Add bottom hint bar text.

### Task 7: Combat/data integrity updates and CSV validation

**Files:**
- Modify: `game/systems/battle/engine.py`
- Modify: `game/assets/core/data_loader.py`
- Modify: `game/tools/validate_csv.py`
- Modify: `game/assets/data/csv/skill_progression.csv` (if needed)

Steps:
1. Ensure player/Airi always have at least one skill at LV1 fallback.
2. Keep battle loop functional skill->damage/status->victory->rewards->return.
3. Extend validator for skill and monster cross references.

### Task 8: Docs, verification, commit, push

**Files:**
- Modify: `README.md`

Steps:
1. Add runbook: install deps, fetch assets, generate icons, validate CSV, run game, debug keys.
2. Run pytest and fix failures.
3. Smoke-run game path with goblin encounter and menu/input checks.
4. Commit changes and push to GitHub remote `main`.
