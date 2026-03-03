# Window GUI Migration (Rich layout parity path)

This plan implements a terminal-free host while preserving existing Rich layout definitions and menu behavior.

## What is now in the repository

### Phase 1: UI transport separation (foundation)
- Added explicit transport contracts:
  - `RenderTarget`
  - `InputSource`
  - `DisplayController`
- Added frame model primitives (`Cell`, fixed grid frame buffer).

### Phase 2: Rich offscreen renderer
- Added `RichOffscreenRenderer` that renders Rich markup to a fixed cell grid.
- Maintains char-cell geometry and carries style attributes (FG/BG + bold).

### Phase 3: Native window host
- Added pygame-based native window host (`PygameWindowHost`) as borderless/fullscreen-capable shell.
- Draws per-cell background + glyph, mapping logical key events.

### Phase 4: Input migration (menu layer)
- Added logical key mapping (`UP/DOWN/ENTER/ESC` + `F11` fullscreen toggle).
- Added initial windowed menu runtime that returns menu choice.
- Added menu transport backend hooks in `menu_controls` (`arrow_menu`, `clear_screen`, prompt APIs) for non-terminal delegation.
- Migrated `main_menu`, `load_menu`, and character-creation pause prompts to transport-aware prompt handling.
- Migrated character-creation free-text entry prompts (name/profile values) to transport-aware `prompt_input`.
- Added concrete `WindowMenuTransportBackend` (pygame + rich offscreen) for window-hosted `arrow_menu` / `read_key` / `prompt_input` flows.
- Backend is implemented but not yet globally activated while remaining terminal-rendered screens are being ported.
- Added scoped runtime activation for `New Game` character-creation path under `RPG_WINDOW_SHELL=1`, with safe fallback/reset.
- Expanded scoped runtime activation to `Continue` and `Import` menu flows under `RPG_WINDOW_SHELL=1`.
- Expanded scoped activation to gameplay-loop entry (`run_game_loop` / `run_live_game_loop`) so top-level gameplay menus can flow through window transport during migration.
- Migrated `game_loop` continue/pause prompts to transport-aware `prompt_enter` to reduce direct terminal input usage in-loop.
- Migrated `live_game_loop` prompt-entry paths (combat/world spellcasting, item use, root action input, attunement swap) to transport-aware `prompt_input`.
- Migrated `main_menu` display-mode confirmation fallback and `rolling_ui` continue prompts to transport-aware `prompt_input`.
- Migrated legacy `cli` character-creation/game-loop prompt reads to transport-aware `prompt_input`.
- Normalized window transport `prompt_input` cancel semantics (ESC/QUIT returns empty input) to align with terminal prompt behavior.
- Migrated `game_loop` recovery-status note from direct terminal print to `arrow_menu` footer hint so it renders via transport-backed menus.

### Phase 5: Settings persistence
- Added persisted window settings file with:
  - `display_mode` (`windowed|maximized|fullscreen`)
  - `font_scale`

### Runtime switch
- Added `RPG_WINDOW_SHELL=1` to route startup into the native window menu shell.
- Window shell now owns root route selection and handles `Settings`, `Help`, and `Credits` directly in-window.
- `Continue` and `Import Exported Character` now support in-window selection/picking before gameplay handoff.
- `New Game` and downstream gameplay/character-creation screens still transition into terminal-backed flows during ongoing migration.

## Remaining work for full parity

1. Replace remaining `print/input/clear_screen/msvcrt` flows in all screens with transport-backed adapters.
2. Convert each screen (character creation, class details, settings, help, in-game loops) to offscreen-rich frames.
3. Add fixed bundled font selection and metrics lock.
4. Add display apply/revert UX with timeout confirmation.
5. Package with windowed executable mode and bundled assets.
6. Add screenshot baseline comparator against `Golden Screenshots`.

## Suggested integration order (file-by-file)

1. `src/rpg/presentation/menu_controls.py` (introduce adapter layer; preserve existing API).
2. `src/rpg/presentation/character_creation_ui.py` (migrate key entry + panels).
3. `src/rpg/presentation/load_menu.py` (same menu transport).
4. `src/rpg/presentation/game_loop.py` and `src/rpg/presentation/live_game_loop.py`.
5. `src/rpg/presentation/windowing/window_menu.py` -> replace temporary bridge and become canonical root UI.
6. `src/rpg/presentation/music.py` + `sound_effects.py` (ensure event loop-safe calls).

## Notes
- Pixel-perfect parity still depends on bundling an exact monospace font and controlling DPI behavior.
- Current implementation is the migration scaffold with a working window-hosted menu.
