from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
import random
from queue import Empty, Queue
import threading
import time
from typing import Any, Callable

from rpg.presentation import game_loop as legacy_loop
from rpg.presentation.sound_effects import SoundEffects, get_sound_effects

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
except Exception:  # pragma: no cover - optional dependency fallback
    Console = None
    Layout = None
    Live = None
    Panel = None
    Table = None


EventHandler = Callable[["DeferredEvent"], str | list[str] | None]


@dataclass(slots=True)
class DeferredEvent:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    label: str = "Background Task"
    created_at: float = field(default_factory=time.time)


class AsyncEventQueue:
    """Thread-backed deferred event queue for non-critical side effects."""

    def __init__(self, on_message: Callable[[str], None]) -> None:
        self._queue: Queue[DeferredEvent] = Queue()
        self._handlers: dict[str, list[EventHandler]] = {}
        self._on_message = on_message
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pending_count = 0
        self._processed_count = 0
        self._active_label = "Idle"

    def register_handler(self, event_kind: str, handler: EventHandler) -> None:
        self._handlers.setdefault(str(event_kind), []).append(handler)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, name="moonlight-deferred-events", daemon=True)
        self._thread.start()

    def stop(self, timeout_s: float = 1.2) -> None:
        self._running = False
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout_s)

    def publish(self, event_kind: str, payload: dict[str, Any] | None = None, *, label: str = "Background Task") -> None:
        event = DeferredEvent(kind=str(event_kind), payload=dict(payload or {}), label=str(label or "Background Task"))
        with self._lock:
            self._pending_count += 1
        self._queue.put(event)

    def status(self) -> tuple[int, int, str]:
        with self._lock:
            return self._pending_count, self._processed_count, self._active_label

    def _worker(self) -> None:
        while self._running or not self._queue.empty():
            try:
                event = self._queue.get(timeout=0.1)
            except Empty:
                continue

            with self._lock:
                self._active_label = event.label

            handlers = list(self._handlers.get(event.kind, [])) + list(self._handlers.get("*", []))
            if not handlers:
                handlers = [self._default_handler]

            try:
                for handler in handlers:
                    result = handler(event)
                    if isinstance(result, str):
                        self._on_message(result)
                    elif isinstance(result, list):
                        for row in result:
                            message = str(row or "").strip()
                            if message:
                                self._on_message(message)
            except Exception as exc:
                self._on_message(f"[deferred-error] {event.kind}: {exc}")
            finally:
                with self._lock:
                    self._pending_count = max(0, self._pending_count - 1)
                    self._processed_count += 1
                    self._active_label = "Idle"
                self._queue.task_done()

    @staticmethod
    def _default_handler(event: DeferredEvent) -> str:
        time.sleep(0.08)
        kind = str(event.kind).replace("_", " ")
        return f"Deferred complete: {kind}."


@dataclass(slots=True)
class LiveGameContext:
    game_service: Any
    character_id: int
    log_lines: deque[str] = field(default_factory=lambda: deque(maxlen=20))
    exploration_lines: deque[str] = field(default_factory=lambda: deque(maxlen=10))
    combat_lines: deque[str] = field(default_factory=lambda: deque(maxlen=12))
    event_queue: AsyncEventQueue | None = None
    should_exit: bool = False
    ui_console: Any | None = None
    ui_live: Any | None = None
    ui_density: str = "standard"
    sound_effects: SoundEffects = field(default_factory=get_sound_effects)

    def append_log(self, message: str) -> None:
        row = str(message or "").strip()
        if not row:
            return
        timestamp = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{timestamp}] {row}")

    def play_sound(self, event: str) -> None:
        self.sound_effects.play(event)


class GameState(ABC):
    @abstractmethod
    def render(self, ctx: LiveGameContext):
        raise NotImplementedError

    @abstractmethod
    def handle_input(self, user_input: str, ctx: LiveGameContext) -> "GameState":
        raise NotImplementedError


class RootState(GameState):
    def render(self, ctx: LiveGameContext):
        header, world_summary = _build_header_lines(ctx)
        pending, processed, active = ctx.event_queue.status() if ctx.event_queue is not None else (0, 0, "Idle")
        header_size = _panel_size(ctx, base=5, min_size=4, max_size=7)
        footer_size = _panel_size(ctx, base=5, min_size=4, max_size=7)

        if Layout is None or Panel is None:
            log_body = "\n".join(list(ctx.log_lines) or ["No events yet."])
            return (
                f"{header}\n{world_summary}\n\n"
                f"{log_body}\n\n"
                "[1] Explore Dashboard  [2] Travel  [3] Rest  [4] Inventory  [5] Character  [6] Legacy Act\n"
                f"{_command_footer(ctx, local='Shortcuts: 1-6 or E/T/R/I/C/A', include_back=False, include_quit=True)}\n"
                f"Background: pending={pending} processed={processed} active={active}"
            )

        layout = Layout(name="root")
        layout.split_column(
            Layout(name="header", size=header_size),
            Layout(name="main"),
            Layout(name="footer", size=footer_size),
        )

        layout["header"].update(
            Panel.fit(
                f"{header}\n{world_summary}",
                title="[bold yellow]Realm Status[/bold yellow]",
                border_style="cyan",
            )
        )

        body_lines = list(ctx.log_lines) or ["No events yet."]
        layout["main"].update(
            Panel(
                "\n".join(_cap_lines(body_lines, limit=_line_budget(ctx, fallback=18, min_size=8, max_size=30))),
                title="[bold yellow]Adventure Log[/bold yellow]",
                border_style="green",
            )
        )

        layout["footer"].update(
            Panel.fit(
                "[1] Explore Dashboard  [2] Travel  [3] Rest  [4] Inventory  [5] Character  [6] Legacy Act\n"
                "Type option number, then press ENTER.\n"
                f"{_command_footer(ctx, local='Shortcuts: E/T/R/I/C/A', include_back=False, include_quit=True)}\n"
                f"Background Queue: pending={pending} processed={processed} active={active}",
                title="[bold yellow]Commands[/bold yellow]",
                border_style="cyan",
            )
        )
        return layout

    def handle_input(self, user_input: str, ctx: LiveGameContext) -> GameState:
        choice = str(user_input or "").strip().lower()
        if _handle_density_toggle(choice, ctx):
            return self
        if choice in {"q", "quit", "exit"}:
            return QuitConfirmState()
        if choice in {"c", "char", "character"}:
            return CharacterSheetState()
        if choice in {"a", "act", "legacy"}:
            return _handle_act(ctx)
        if choice in {"e", "explore"}:
            return ExplorationState()
        if choice in {"i", "inv", "inventory"}:
            return InventoryState()
        if choice in {"r", "rest"}:
            try:
                result = ctx.game_service.short_rest_intent(ctx.character_id)
                for line in list(getattr(result, "messages", []) or ["You pause and recover."]):
                    ctx.append_log(str(line))
                ctx.play_sound("action_success")
            except Exception as exc:
                ctx.append_log(f"Rest failed: {exc}")
                ctx.play_sound("error")
            _queue_narrative_task(ctx, "rest", "Updating camp journal")
            return self
        if choice in {"t", "travel"}:
            choice = "2"
        if choice == "1":
            return ExplorationState()
        if choice == "2":
            try:
                destinations = list(ctx.game_service.get_travel_destinations_intent(ctx.character_id) or [])
            except Exception as exc:
                ctx.append_log(f"Travel options unavailable: {exc}")
                return self
            if not destinations:
                try:
                    result = ctx.game_service.travel_intent(ctx.character_id)
                    for line in list(getattr(result, "messages", []) or ["You travel onward."]):
                        ctx.append_log(str(line))
                    ctx.play_sound("action_success")
                except Exception as exc:
                    ctx.append_log(f"Travel failed: {exc}")
                    ctx.play_sound("error")
                _queue_narrative_task(ctx, "travel", "Updating route chronicle")
                return self
            return TravelSelectState(destinations)
        if choice == "3":
            try:
                result = ctx.game_service.short_rest_intent(ctx.character_id)
                for line in list(getattr(result, "messages", []) or ["You pause and recover."]):
                    ctx.append_log(str(line))
                ctx.play_sound("action_success")
            except Exception as exc:
                ctx.append_log(f"Rest failed: {exc}")
                ctx.play_sound("error")
            _queue_narrative_task(ctx, "rest", "Updating camp journal")
            return self
        if choice == "4":
            return InventoryState()
        if choice == "5":
            return CharacterSheetState()
        if choice == "6":
            return _handle_act(ctx)

        ctx.append_log("Unknown command. Choose 1-6 or Q.")
        return self


class ExplorationState(GameState):
    def render(self, ctx: LiveGameContext):
        header, world_summary = _build_header_lines(ctx)
        map_lines, legend_lines = _build_exploration_map_lines(ctx)
        env = _safe_get_exploration_env(ctx)
        header_size = _panel_size(ctx, base=5, min_size=4, max_size=7)
        footer_size = _panel_size(ctx, base=5, min_size=4, max_size=7)

        narrative_lines = list(ctx.exploration_lines) or ["Survey the area to reveal threats, clues, and paths."]
        sense_lines = [
            f"Light: {env.get('light_level', 'Unknown')}",
            f"Suspicion: {env.get('detection_state', 'Unaware')}",
        ]
        note = str(env.get("detection_note", "") or "").strip()
        if note:
            sense_lines.append(note)

        if Layout is None or Panel is None:
            lines = [header, world_summary, "", "[LOCAL MAP]"]
            lines.extend(map_lines)
            lines.append("")
            lines.append("[NARRATIVE & SENSES]")
            lines.extend(narrative_lines[-6:])
            lines.extend(sense_lines)
            lines.append("")
            lines.append("[E] Explore  [M] Cast Spell  [T] Travel  [I] Inventory  [R] Rest  [D] Dialogue  [B] Back")
            return "\n".join(lines)

        layout = Layout(name="explore")
        layout.split_column(
            Layout(name="header", size=header_size),
            Layout(name="body"),
            Layout(name="footer", size=footer_size),
        )
        layout["body"].split_row(
            Layout(name="map", ratio=1),
            Layout(name="narrative", ratio=2),
        )

        layout["header"].update(
            Panel.fit(
                f"{header}\n{world_summary}",
                title="[bold yellow]Exploration Dashboard[/bold yellow]",
                border_style="cyan",
            )
        )

        map_text = "\n".join(map_lines + [""] + legend_lines)
        layout["map"].update(Panel(map_text, title="[bold cyan]Local Map[/bold cyan]", border_style="cyan"))

        narrative_block = "\n".join(
            _cap_lines(narrative_lines, limit=_line_budget(ctx, fallback=8, min_size=5, max_size=14))
            + [""]
            + [f"[dim]{row}[/dim]" for row in _cap_lines(sense_lines, limit=_line_budget(ctx, fallback=3, min_size=2, max_size=5))]
        )
        layout["narrative"].update(
            Panel(
                narrative_block,
                title="[bold green]Narrative & Senses[/bold green]",
                border_style="green",
            )
        )

        layout["footer"].update(
            Panel.fit(
                "[E] Explore  [M] Cast Spell  [T] Travel  [I] Inventory  [R] Rest  [D] Dialogue  [B] Back\n"
                "Explore may trigger encounters and shift directly into Tactical Combat HUD.\n"
                f"{_command_footer(ctx, local='Local: E/M/T/I/R/D/B', include_back=True, include_quit=True)}",
                title="[bold yellow]Actions[/bold yellow]",
                border_style="magenta",
            )
        )
        return layout

    def handle_input(self, user_input: str, ctx: LiveGameContext) -> GameState:
        raw = str(user_input or "").strip().lower()
        if _handle_density_toggle(raw, ctx):
            return self
        if raw in {"q", "quit", "exit"}:
            return QuitConfirmState()
        if raw in {"c", "char", "character"}:
            return CharacterSheetState()
        if raw in {"b", "back", "esc"}:
            return RootState()
        if raw in {"i", "inv", "inventory", "4"}:
            return InventoryState(return_state=ExplorationState())
        if raw in {"t", "travel", "2"}:
            try:
                destinations = list(ctx.game_service.get_travel_destinations_intent(ctx.character_id) or [])
            except Exception as exc:
                ctx.append_log(f"Travel options unavailable: {exc}")
                return self
            if not destinations:
                ctx.append_log("No travel destinations currently available.")
                return self
            return TravelSelectState(destinations)
        if raw in {"r", "rest", "3"}:
            try:
                result = ctx.game_service.short_rest_intent(ctx.character_id)
                for line in list(getattr(result, "messages", []) or ["You rest and recover."]):
                    msg = str(line)
                    ctx.append_log(msg)
                    ctx.exploration_lines.append(msg)
            except Exception as exc:
                ctx.append_log(f"Rest failed: {exc}")
            return self
        if raw in {"d", "dialogue", "talk"}:
            try:
                location_context = ctx.game_service.get_location_context_intent(ctx.character_id)
                location_type = str(getattr(location_context, "location_type", "") or "").strip().lower()
            except Exception:
                location_type = ""
            if location_type != "town":
                ctx.append_log("Dialogue overlay is available in town districts.")
                return self
            return DialogueOverlayState(return_state=ExplorationState())
        if raw in {"m", "magic", "spell", "cast"}:
            return _handle_world_spellcast(ctx)
        if raw in {"e", "explore", "1", "s", "search"}:
            return _handle_explore_step(ctx)

        ctx.append_log("Exploration commands: E, M, T, I, R, D, B.")
        return self


class InventoryState(GameState):
    def __init__(self, *, return_state: GameState | None = None) -> None:
        self._cursor = 0
        self._attune_cursor = 0
        self._return_state = return_state or RootState()

    def render(self, ctx: LiveGameContext):
        header, world_summary = _build_header_lines(ctx)
        view = _safe_equipment_view(ctx)
        items = list(getattr(view, "inventory_items", []) or [])
        equipped = dict(getattr(view, "equipped_slots", {}) or {})
        header_size = _panel_size(ctx, base=5, min_size=4, max_size=7)
        footer_size = _panel_size(ctx, base=5, min_size=4, max_size=7)

        if items:
            self._cursor = max(0, min(self._cursor, len(items) - 1))
            selected = items[self._cursor]
        else:
            self._cursor = 0
            selected = None

        attuned_items = _safe_attuned_items(ctx)
        left_rows = _inventory_left_lines(items, self._cursor)
        right_rows = _inventory_detail_lines(selected, equipped, attuned_items)

        if Layout is None or Panel is None:
            lines = [header, world_summary, "", "[BACKPACK]"] + left_rows + [""] + ["[DETAILS]"] + right_rows
            lines.append("")
            lines.append("[J/K] Move  [E] Equip  [D] Drop  [U] Unequip Slot  [A] Swap Attunement  [B] Back")
            return "\n".join(lines)

        layout = Layout(name="inventory")
        layout.split_column(
            Layout(name="header", size=header_size),
            Layout(name="body"),
            Layout(name="footer", size=footer_size),
        )
        layout["body"].split_row(Layout(name="bag", ratio=1), Layout(name="detail", ratio=2))

        layout["header"].update(
            Panel.fit(
                f"{header}\n{world_summary}",
                title="[bold yellow]Inventory & Equipment[/bold yellow]",
                border_style="cyan",
            )
        )
        layout["bag"].update(
            Panel(
                "\n".join(_cap_lines(left_rows, limit=_line_budget(ctx, fallback=20, min_size=8, max_size=32))),
                title="[bold cyan]Backpack[/bold cyan]",
                border_style="cyan",
            )
        )
        layout["detail"].update(
            Panel(
                "\n".join(_cap_lines(right_rows, limit=_line_budget(ctx, fallback=20, min_size=8, max_size=32))),
                title="[bold green]Item Details[/bold green]",
                border_style="green",
            )
        )
        layout["footer"].update(
            Panel.fit(
                "[J/K] Move  [E] Equip  [D] Drop  [U] Unequip Slot  [A] Swap Attunement  [B] Back\n"
                "Paper-doll slots tracked: Weapon, Armor, Trinket.\n"
                f"{_command_footer(ctx, local='Local: J/K/E/D/U/A/B', include_back=True, include_quit=True)}",
                title="[bold yellow]Actions[/bold yellow]",
                border_style="magenta",
            )
        )
        return layout

    def handle_input(self, user_input: str, ctx: LiveGameContext) -> GameState:
        raw = str(user_input or "").strip().lower()
        view = _safe_equipment_view(ctx)
        items = list(getattr(view, "inventory_items", []) or [])

        if _handle_density_toggle(raw, ctx):
            return self
        if raw in {"q", "quit", "exit"}:
            return QuitConfirmState()
        if raw in {"c", "char", "character"}:
            return CharacterSheetState()

        if raw in {"b", "back", "q", "esc"}:
            return self._return_state
        if raw in {"k", "up", "w"}:
            if items:
                self._cursor = max(0, self._cursor - 1)
            return self
        if raw in {"j", "down", "s"}:
            if items:
                self._cursor = min(max(0, len(items) - 1), self._cursor + 1)
            return self

        if not items:
            ctx.append_log("Inventory is empty.")
            return self

        self._cursor = max(0, min(self._cursor, len(items) - 1))
        selected = items[self._cursor]
        selected_name = str(getattr(selected, "name", "") or "")
        selected_slot = str(getattr(selected, "slot", "") or "").strip().lower()

        if raw in {"e", "equip"}:
            try:
                result = ctx.game_service.equip_inventory_item_intent(ctx.character_id, selected_name)
                for line in list(getattr(result, "messages", []) or []):
                    ctx.append_log(str(line))
            except Exception as exc:
                ctx.append_log(f"Equip failed: {exc}")
            return self

        if raw in {"d", "drop"}:
            try:
                result = ctx.game_service.drop_inventory_item_intent(ctx.character_id, selected_name)
                for line in list(getattr(result, "messages", []) or []):
                    ctx.append_log(str(line))
            except Exception as exc:
                ctx.append_log(f"Drop failed: {exc}")
            return self

        if raw in {"u", "unequip"}:
            slot_name = selected_slot if selected_slot in {"weapon", "armor", "trinket"} else ""
            if not slot_name:
                ctx.append_log("Select an equipped weapon/armor/trinket item to unequip its slot.")
                return self
            try:
                result = ctx.game_service.unequip_slot_intent(ctx.character_id, slot_name)
                for line in list(getattr(result, "messages", []) or []):
                    ctx.append_log(str(line))
            except Exception as exc:
                ctx.append_log(f"Unequip failed: {exc}")
            return self

        if raw in {"a", "attune", "swap"}:
            attuned = _safe_attuned_items(ctx)
            old_item = ""
            if attuned:
                if len(attuned) == 1:
                    old_item = str(attuned[0])
                else:
                    console = ctx.ui_console
                    if console is not None:
                        prompt_lines = ["Swap attunement - pick currently attuned item:"]
                        for index, row in enumerate(attuned, start=1):
                            prompt_lines.append(f"[{index}] {row}")
                        prompt_lines.append("Enter number (or press ENTER to cancel)")
                        response = console.input("\n".join(prompt_lines) + "\n").strip()
                        if not response:
                            ctx.append_log("Attunement swap canceled.")
                            return self
                        if response.isdigit():
                            picked = int(response) - 1
                            if 0 <= picked < len(attuned):
                                old_item = str(attuned[picked])
                        if not old_item:
                            old_item = str(response)
                if not old_item:
                    old_item = str(attuned[0])
            else:
                ctx.append_log("No currently attuned items available to swap.")
                return self

            try:
                result = ctx.game_service.swap_attuned_item_intent(ctx.character_id, old_item, selected_name)
                for line in list(getattr(result, "messages", []) or []):
                    ctx.append_log(str(line))
            except Exception as exc:
                ctx.append_log(f"Attunement swap failed: {exc}")
            return self

        ctx.append_log("Inventory commands: J/K, E, D, U, A, B.")
        return self


class CombatState(GameState):
    def __init__(self, player: Any, enemies: list[Any], scene: dict[str, str], *, return_state: GameState | None = None) -> None:
        self._player = player
        self._enemies = list(enemies)
        self._scene = dict(scene)
        self._return_state = return_state or ExplorationState()
        self._resolved = False
        self._result_lines: list[str] = []

    def render(self, ctx: LiveGameContext):
        if self._resolved:
            if Layout is None or Panel is None:
                return "\n".join(self._result_lines + ["", "Press ENTER to return."])
            return Panel(
                "\n".join(self._result_lines or ["Combat complete."]),
                title="[bold yellow]Combat Resolution[/bold yellow]",
                border_style="cyan",
            )

        options = ["Melee Attack", "Cast Spell", "Use Item", "Disengage"]
        header, world_summary = _build_header_lines(ctx)
        return _render_tactical_hud_layout(
            header=header,
            world_summary=world_summary,
            player=self._player,
            enemies=self._enemies,
            scene=self._scene,
            recent_lines=list(ctx.combat_lines),
            options=options,
            title="Tactical Combat HUD",
            footer="Press ENTER to engage encounter. During combat, choose actions by number.",
        )

    def handle_input(self, user_input: str, ctx: LiveGameContext) -> GameState:
        raw = str(user_input or "").strip().lower()
        if _handle_density_toggle(raw, ctx):
            return self
        if raw in {"q", "quit", "exit"}:
            return QuitConfirmState()
        if self._resolved:
            return self._return_state

        lines = _resolve_combat_with_tactical_hud(
            ctx,
            player=self._player,
            enemies=self._enemies,
            scene=self._scene,
        )
        self._result_lines = lines or ["Combat concluded."]
        self._resolved = True
        return self


class DialogueOverlayState(GameState):
    def __init__(self, *, return_state: GameState | None = None) -> None:
        self._return_state = return_state or ExplorationState()
        self._selected_npc_id: str = ""
        self._selected_npc_name: str = ""
        self._feedback_lines: deque[str] = deque(maxlen=5)

    def _town_npcs(self, ctx: LiveGameContext) -> list[Any]:
        try:
            town_view = ctx.game_service.get_town_view_intent(ctx.character_id)
        except Exception:
            return []
        return list(getattr(town_view, "npcs", []) or [])

    def _selected_npc(self, ctx: LiveGameContext):
        if not self._selected_npc_id:
            return None
        for npc in self._town_npcs(ctx):
            if str(getattr(npc, "id", "") or "") == self._selected_npc_id:
                return npc
        return None

    def render(self, ctx: LiveGameContext):
        header, world_summary = _build_header_lines(ctx)
        map_lines, legend_lines = _build_exploration_map_lines(ctx)
        narrative_lines = list(ctx.exploration_lines) or ["The town breathes around your conversation."]
        header_size = _panel_size(ctx, base=5, min_size=4, max_size=7)

        npc = self._selected_npc(ctx)
        if npc is None:
            npc_lines = []
            npcs = self._town_npcs(ctx)
            for index, row in enumerate(npcs, start=1):
                temperament = str(getattr(row, "temperament", "Neutral") or "Neutral")
                relationship = int(getattr(row, "relationship", 0) or 0)
                disposition = _relationship_disposition(relationship)
                npc_lines.append(f"[{index}] {getattr(row, 'name', 'Unknown')} ({temperament}) [{disposition}]")
            if not npc_lines:
                npc_lines = ["No available NPCs in this district."]
            dialogue_title = "Dialogue Overlay"
            dialogue_body = "\n".join(
                [
                    "Choose someone to speak with:",
                    *npc_lines,
                    "",
                    "Type number to open dialogue, or B to return.",
                ]
            )
        else:
            interaction = ctx.game_service.get_npc_interaction_intent(ctx.character_id, str(getattr(npc, "id", "") or ""))
            session = ctx.game_service.get_dialogue_session_intent(ctx.character_id, str(getattr(npc, "id", "") or ""))
            choice_rows = list(getattr(session, "choices", []) or [])
            options: list[str] = []
            for index, row in enumerate(choice_rows, start=1):
                label = str(getattr(row, "label", "Direct") or "Direct")
                if bool(getattr(row, "available", False)):
                    options.append(f"[{index}] {label}")
                else:
                    lock_hint = str(getattr(row, "locked_reason", "Locked") or "Locked")
                    options.append(f"[{index}] {label} [Locked: {lock_hint}]")

            relationship = int(getattr(interaction, "relationship", 0) or 0)
            disposition = _relationship_disposition(relationship)
            challenge_progress = int(getattr(session, "challenge_progress", 0) or 0)
            challenge_target = int(getattr(session, "challenge_target", 3) or 3)
            challenge_line = f"Challenge: {challenge_progress}/{max(1, challenge_target)}"

            feedback = list(self._feedback_lines)
            if feedback:
                feedback_block = ["", "Recent Outcome:", *[f"- {row}" for row in feedback]]
            else:
                feedback_block = []

            dialogue_title = f"{getattr(interaction, 'npc_name', 'NPC')} [{disposition}]"
            dialogue_body = "\n".join(
                [
                    challenge_line,
                    str(getattr(session, "greeting", "...") or "..."),
                    "",
                    *_cap_lines(options, limit=_line_budget(ctx, fallback=6, min_size=3, max_size=12)),
                    "",
                    "Type option number, B to pick another NPC, or ESC to close overlay.",
                    *feedback_block,
                ]
            )

        if Layout is None or Panel is None:
            lines = [header, world_summary, "", "[dim]Background exploration view...[/dim]"]
            lines.extend([f"[dim]{row}[/dim]" for row in map_lines])
            lines.append("")
            lines.extend([f"[dim]{row}[/dim]" for row in narrative_lines[-4:]])
            lines.append("")
            lines.append(f"[{dialogue_title}]")
            lines.append(dialogue_body)
            return "\n".join(lines)

        layout = Layout(name="dialogue-overlay")
        layout.split_column(
            Layout(name="background", ratio=3),
            Layout(name="dialogue", ratio=2),
        )

        bg = Layout(name="bg")
        bg.split_column(
            Layout(name="header", size=header_size),
            Layout(name="body"),
        )
        bg["body"].split_row(Layout(name="map", ratio=1), Layout(name="narrative", ratio=2))

        bg["header"].update(
            Panel.fit(
                f"[dim]{header}[/dim]\n[dim]{world_summary}[/dim]",
                title="[dim]Exploration (Dimmed)[/dim]",
                border_style="bright_black",
            )
        )
        bg["map"].update(
            Panel(
                "\n".join([f"[dim]{row}[/dim]" for row in _cap_lines(map_lines + [""] + legend_lines, limit=_line_budget(ctx, fallback=10, min_size=5, max_size=16))]),
                border_style="bright_black",
            )
        )
        bg["narrative"].update(
            Panel(
                "\n".join([f"[dim]{row}[/dim]" for row in _cap_lines(narrative_lines, limit=_line_budget(ctx, fallback=8, min_size=4, max_size=14))]),
                border_style="bright_black",
            )
        )

        layout["background"].update(bg)
        layout["dialogue"].update(
            Panel(
                "\n".join(_cap_lines(str(dialogue_body).splitlines(), limit=_line_budget(ctx, fallback=10, min_size=6, max_size=18))),
                title=f"[bold yellow]{dialogue_title}[/bold yellow]",
                subtitle=f"[dim]{_command_footer(ctx, local='Local: number/B/ESC', include_back=True, include_quit=True)}[/dim]",
                subtitle_align="left",
                border_style="cyan",
            )
        )
        return layout

    def handle_input(self, user_input: str, ctx: LiveGameContext) -> GameState:
        raw = str(user_input or "").strip().lower()
        if _handle_density_toggle(raw, ctx):
            return self
        if raw in {"c", "char", "character"}:
            return CharacterSheetState()
        if raw in {"esc", "q", "quit"}:
            if raw in {"q", "quit"}:
                return QuitConfirmState()
            return self._return_state

        npc = self._selected_npc(ctx)
        if npc is None:
            if raw in {"b", "back"}:
                return self._return_state
            if not raw.isdigit():
                ctx.append_log("Dialogue: enter an NPC number, or B to return.")
                return self
            npcs = self._town_npcs(ctx)
            idx = int(raw) - 1
            if idx < 0 or idx >= len(npcs):
                ctx.append_log("Dialogue: NPC selection out of range.")
                return self
            selected = npcs[idx]
            self._selected_npc_id = str(getattr(selected, "id", "") or "")
            self._selected_npc_name = str(getattr(selected, "name", "NPC") or "NPC")
            self._feedback_lines.clear()
            return self

        if raw in {"b", "back"}:
            self._selected_npc_id = ""
            self._selected_npc_name = ""
            self._feedback_lines.clear()
            return self

        if not raw.isdigit():
            ctx.append_log("Dialogue: choose a dialogue option number, or B to pick another NPC.")
            return self

        session = ctx.game_service.get_dialogue_session_intent(ctx.character_id, self._selected_npc_id)
        choice_rows = list(getattr(session, "choices", []) or [])
        idx = int(raw) - 1
        if idx < 0 or idx >= len(choice_rows):
            ctx.append_log("Dialogue: option out of range.")
            return self
        selected_choice = choice_rows[idx]
        if not bool(getattr(selected_choice, "available", False)):
            reason = str(getattr(selected_choice, "locked_reason", "Choice is unavailable.") or "Choice is unavailable.")
            self._feedback_lines.clear()
            self._feedback_lines.append(reason)
            ctx.append_log(f"Dialogue locked: {reason}")
            return self

        outcome = ctx.game_service.submit_dialogue_choice_intent(
            ctx.character_id,
            self._selected_npc_id,
            str(getattr(selected_choice, "choice_id", "direct") or "direct"),
        )
        messages = [str(row) for row in list(getattr(outcome, "messages", []) or []) if str(row).strip()]
        if not messages:
            messages = ["The conversation shifts, but yields no clear result."]
        self._feedback_lines.clear()
        for row in messages[:5]:
            self._feedback_lines.append(row)
        for row in messages[:2]:
            ctx.append_log(f"{self._selected_npc_name}: {row}")
        return self


class TravelSelectState(GameState):
    def __init__(self, destinations: list[Any]) -> None:
        self._destinations = list(destinations)

    def render(self, ctx: LiveGameContext):
        header, world_summary = _build_header_lines(ctx)
        lines = [f"[{index}] {getattr(row, 'name', 'Unknown')} — {getattr(row, 'preview', '')}" for index, row in enumerate(self._destinations, start=1)]
        lines.append("[B] Back")
        header_size = _panel_size(ctx, base=5, min_size=4, max_size=7)
        footer_size = _panel_size(ctx, base=4, min_size=3, max_size=6)

        if Layout is None or Panel is None:
            return f"{header}\n{world_summary}\n\n" + "\n".join(lines)

        layout = Layout(name="travel")
        layout.split_column(Layout(name="header", size=header_size), Layout(name="main"), Layout(name="footer", size=footer_size))
        layout["header"].update(Panel.fit(f"{header}\n{world_summary}", title="[bold yellow]Travel[/bold yellow]", border_style="cyan"))
        layout["main"].update(Panel("\n".join(_cap_lines(lines, limit=_line_budget(ctx, fallback=14, min_size=6, max_size=24))), title="[bold yellow]Destinations[/bold yellow]", border_style="magenta"))
        layout["footer"].update(Panel.fit(f"Type destination number or B to go back.\n{_command_footer(ctx, local='Local: number/B', include_back=True, include_quit=True)}", border_style="cyan"))
        return layout

    def handle_input(self, user_input: str, ctx: LiveGameContext) -> GameState:
        raw = str(user_input or "").strip().lower()
        if _handle_density_toggle(raw, ctx):
            return self
        if raw in {"q", "quit", "exit"}:
            return QuitConfirmState()
        if raw in {"c", "char", "character"}:
            return CharacterSheetState()
        if raw in {"b", "back", "esc"}:
            return RootState()
        if not raw.isdigit():
            ctx.append_log("Enter a destination number, or B to go back.")
            return self

        selected = int(raw) - 1
        if selected < 0 or selected >= len(self._destinations):
            ctx.append_log("Destination out of range.")
            return self

        row = self._destinations[selected]
        destination_id = int(getattr(row, "location_id", 0) or 0)
        try:
            result = ctx.game_service.travel_intent(ctx.character_id, destination_id=destination_id)
            for line in list(getattr(result, "messages", []) or [f"You travel to {getattr(row, 'name', 'your destination')}."]):
                ctx.append_log(str(line))
        except Exception as exc:
            ctx.append_log(f"Travel failed: {exc}")
        _queue_narrative_task(ctx, "travel", "Synthesizing travel flavour")
        return RootState()


class CharacterSheetState(GameState):
    def render(self, ctx: LiveGameContext):
        header, world_summary = _build_header_lines(ctx)
        header_size = _panel_size(ctx, base=5, min_size=4, max_size=7)
        footer_size = _panel_size(ctx, base=4, min_size=3, max_size=6)
        try:
            sheet = ctx.game_service.get_character_sheet_intent(ctx.character_id)
            sheet_lines = [
                f"Name: {getattr(sheet, 'name', 'Unknown')}",
                f"Level: {getattr(sheet, 'level', '?')} | XP: {getattr(sheet, 'xp_current', '?')}/{getattr(sheet, 'xp_required', '?')}",
                f"HP: {getattr(sheet, 'hp_current', '?')}/{getattr(sheet, 'hp_max', '?')}",
                f"AC: {getattr(sheet, 'armor_class', '?')}",
            ]
        except Exception as exc:
            sheet_lines = [f"Character sheet unavailable: {exc}"]

        if Layout is None or Panel is None:
            return f"{header}\n{world_summary}\n\n" + "\n".join(sheet_lines)

        layout = Layout(name="character")
        layout.split_column(Layout(name="header", size=header_size), Layout(name="main"), Layout(name="footer", size=footer_size))
        layout["header"].update(Panel.fit(f"{header}\n{world_summary}", title="[bold yellow]Character[/bold yellow]", border_style="cyan"))
        layout["main"].update(Panel("\n".join(_cap_lines(sheet_lines, limit=_line_budget(ctx, fallback=18, min_size=8, max_size=28))), title="[bold yellow]Sheet[/bold yellow]", border_style="green"))
        layout["footer"].update(Panel.fit(f"Press ENTER (or B) to return.\n{_command_footer(ctx, local='Local: ENTER/B', include_back=True, include_quit=True)}", border_style="cyan"))
        return layout

    def handle_input(self, user_input: str, ctx: LiveGameContext) -> GameState:
        raw = str(user_input or "").strip().lower()
        if _handle_density_toggle(raw, ctx):
            return self
        if raw in {"q", "quit", "exit"}:
            return QuitConfirmState()
        return RootState()


class QuitConfirmState(GameState):
    def render(self, ctx: LiveGameContext):
        if Layout is None or Panel is None:
            return "Quit this session? [Y/N]"

        layout = Layout(name="quit")
        layout.split_column(Layout(name="main"), Layout(name="footer", size=4))
        layout["main"].update(
            Panel.fit(
                "[bold magenta]Quit this session?[/bold magenta]\nYour world state remains persisted.",
                title="[bold yellow]Confirm Exit[/bold yellow]",
                border_style="magenta",
            )
        )
        layout["footer"].update(Panel.fit("Type Y to quit or N to continue.", border_style="cyan"))
        return layout

    def handle_input(self, user_input: str, ctx: LiveGameContext) -> GameState:
        raw = str(user_input or "").strip().lower()
        if raw in {"y", "yes"}:
            ctx.should_exit = True
            return self
        if raw in {"n", "no", "", "back"}:
            return RootState()
        return self


def _safe_get_exploration_env(ctx: LiveGameContext) -> dict[str, str]:
    try:
        raw = ctx.game_service.get_exploration_environment_intent(ctx.character_id)
    except Exception:
        return {
            "light_level": "Unknown",
            "detection_state": "Unaware",
            "detection_note": "",
        }
    if not isinstance(raw, dict):
        return {
            "light_level": "Unknown",
            "detection_state": "Unaware",
            "detection_note": "",
        }
    return {
        "light_level": str(raw.get("light_level", "Unknown") or "Unknown"),
        "detection_state": str(raw.get("detection_state", "Unaware") or "Unaware"),
        "detection_note": str(raw.get("detection_note", "") or ""),
    }


def _build_exploration_map_lines(ctx: LiveGameContext) -> tuple[list[str], list[str]]:
    try:
        location_context = ctx.game_service.get_location_context_intent(ctx.character_id)
    except Exception:
        location_context = None

    try:
        destinations = list(ctx.game_service.get_travel_destinations_intent(ctx.character_id) or [])
    except Exception:
        destinations = []

    names = [str(getattr(row, "name", "Unknown") or "Unknown") for row in destinations[:3]]
    while len(names) < 3:
        names.append("Unexplored")

    current_name = str(getattr(location_context, "current_location_name", "Current Position") or "Current Position")
    map_lines = [
        f"   [?] {names[0]}",
        "    |",
        f"[?] {names[1]} -- [X] {current_name}",
        "    |",
        f"   [?] {names[2]}",
    ]
    legend = [
        "X = You",
        "? = Reachable / unexplored route",
    ]
    return map_lines, legend


def _safe_equipment_view(ctx: LiveGameContext):
    try:
        return ctx.game_service.get_equipment_view_intent(ctx.character_id)
    except Exception:
        class _FallbackView:
            equipped_slots: dict[str, str] = {}
            inventory_items: list[Any] = []

        return _FallbackView()


def _inventory_left_lines(items: list[Any], cursor: int) -> list[str]:
    if not items:
        return ["(empty)"]

    groups: dict[str, list[tuple[int, Any]]] = {
        "Weapons": [],
        "Armour": [],
        "Trinkets": [],
        "Other": [],
    }
    for index, row in enumerate(items):
        slot = str(getattr(row, "slot", "") or "").strip().lower()
        if slot == "weapon":
            groups["Weapons"].append((index, row))
        elif slot == "armor":
            groups["Armour"].append((index, row))
        elif slot == "trinket":
            groups["Trinkets"].append((index, row))
        else:
            groups["Other"].append((index, row))

    lines: list[str] = []
    for section in ("Weapons", "Armour", "Trinkets", "Other"):
        rows = groups[section]
        if not rows:
            continue
        lines.append(f"[bold]{section}[/bold]")
        for index, row in rows:
            marker = "▶" if index == cursor else " "
            equipped = " [equipped]" if bool(getattr(row, "equipped", False)) else ""
            lines.append(f"{marker} {getattr(row, 'name', 'Unknown')}{equipped}")
        lines.append("")
    return lines[:-1] if lines and lines[-1] == "" else lines


def _inventory_detail_lines(selected: Any, equipped_slots: dict[str, str], attuned_items: list[str] | None = None) -> list[str]:
    if selected is None:
        return ["Select an item in the backpack pane."]

    name = str(getattr(selected, "name", "Unknown") or "Unknown")
    slot = str(getattr(selected, "slot", "") or "").strip().lower()
    equipable = bool(getattr(selected, "equipable", False))
    equipped = bool(getattr(selected, "equipped", False))

    slot_label = slot.title() if slot else "Carry Item"
    current = str(equipped_slots.get(slot, "(empty)") or "(empty)") if slot else "N/A"
    state = "Equipped" if equipped else ("Can Equip" if equipable else "Not Equipable")

    attuned = [str(row) for row in list(attuned_items or []) if str(row).strip()]
    attuned_summary = ", ".join(attuned[:3]) if attuned else "None"

    return [
        f"Item: [bold]{name}[/bold]",
        f"Slot: {slot_label}",
        f"State: {state}",
        "",
        "[bold]Currently Equipped[/bold]",
        f"{slot_label}: {current}",
        "",
        f"[bold]Attuned[/bold] ({len(attuned)}/3): {attuned_summary}",
        "",
        "[Enter E to equip, D to drop, U to unequip slot, A to swap attunement]",
    ]


def _safe_player_character(ctx: LiveGameContext) -> Any | None:
    game_service = getattr(ctx, "game_service", None)
    if game_service is None:
        return None

    repo = getattr(game_service, "character_repo", None)
    if repo is not None:
        getter = getattr(repo, "get", None)
        if callable(getter):
            try:
                player = getter(int(ctx.character_id))
                if player is not None:
                    return player
            except Exception:
                pass

    require_character = getattr(game_service, "_require_character", None)
    if callable(require_character):
        try:
            player = require_character(int(ctx.character_id))
            if player is not None:
                return player
        except Exception:
            pass
    return None


def _safe_attuned_items(ctx: LiveGameContext) -> list[str]:
    player = _safe_player_character(ctx)
    if player is None:
        return []
    flags = getattr(player, "flags", None)
    if not isinstance(flags, dict):
        return []
    rows = [str(row or "").strip() for row in list(flags.get("attuned_items", []) or [])]
    return [row for row in rows if row]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _hp_bar(current: int, maximum: int, width: int = 10) -> str:
    safe_max = max(1, maximum)
    safe_cur = max(0, min(current, safe_max))
    filled = int(round((safe_cur / safe_max) * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _render_tactical_hud_layout(
    *,
    header: str,
    world_summary: str,
    player: Any,
    enemies: list[Any],
    scene: dict[str, str],
    recent_lines: list[str],
    options: list[str],
    title: str,
    footer: str,
):
    player_name = str(getattr(player, "name", "Adventurer") or "Adventurer")
    initiative = [str(getattr(enemy, "name", "Enemy") or "Enemy") for enemy in enemies]
    initiative.append(player_name)
    initiative_line = " ❯ ".join(
        [f"[dim]{name}[/dim]" if name != player_name else f"[bold green]{name}[/bold green]" for name in initiative]
    )

    player_hp = _safe_int(getattr(player, "hp_current", 0), 0)
    player_hp_max = _safe_int(getattr(player, "hp_max", 1), 1)
    player_ac = _safe_int(getattr(player, "armour_class", 10), 10)
    player_conditions = _player_condition_line(player)

    enemy_lines: list[str] = []
    if enemies:
        for enemy in enemies:
            enemy_hp = _safe_int(getattr(enemy, "hp_current", 0), 0)
            enemy_hp_max = _safe_int(getattr(enemy, "hp_max", 1), 1)
            enemy_lines.append(
                f"{getattr(enemy, 'name', 'Enemy')}: {_hp_bar(enemy_hp, enemy_hp_max)} {enemy_hp}/{enemy_hp_max}"
            )
    else:
        enemy_lines.append("No hostiles visible.")

    left_rows = [
        "[bold]THE VANGUARD[/bold]",
        player_name,
        f"HP: {_hp_bar(player_hp, player_hp_max)} {player_hp}/{player_hp_max}",
        f"AC: {player_ac} | {player_conditions}",
        "",
        "[bold]THE ENEMY[/bold]",
        *enemy_lines,
        "",
        f"Scene: {scene.get('distance', 'close')} | {scene.get('terrain', 'open')} | {scene.get('surprise', 'none')}",
    ]
    log_rows = _cap_lines(recent_lines, limit=10) if recent_lines else ["Awaiting combat events..."]
    action_rows = "  ".join([f"[{i}] {opt}" for i, opt in enumerate(options, start=1)])
    action_rows = _ellipsize_plain(action_rows, max_len=120)

    if Layout is None or Panel is None:
        lines = [header, world_summary, "", f"INITIATIVE: {initiative_line}", ""]
        lines.extend(left_rows)
        lines.append("")
        lines.extend(["> " + row for row in log_rows])
        lines.append("")
        lines.append(footer)
        lines.append(action_rows)
        return "\n".join(lines)

    layout = Layout(name="combat-hud")
    layout.split_column(
        Layout(name="init", size=5),
        Layout(name="body"),
        Layout(name="footer", size=5),
    )
    layout["body"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="log", ratio=2),
    )

    layout["init"].update(
        Panel.fit(
            f"{header}\n{world_summary}\nINITIATIVE: {initiative_line}",
            title=f"[bold yellow]{title}[/bold yellow]",
            border_style="cyan",
        )
    )
    layout["left"].update(Panel("\n".join(left_rows), border_style="cyan"))
    layout["log"].update(Panel("\n".join(["> " + row for row in log_rows]), title="[bold green]Combat Log[/bold green]", border_style="green"))
    layout["footer"].update(
        Panel.fit(
            f"{footer}\n▶ {action_rows}",
            title="[bold magenta]Action Menu[/bold magenta]",
            border_style="magenta",
        )
    )
    return layout


def _player_condition_line(player: Any) -> str:
    flags = getattr(player, "flags", None)
    if not isinstance(flags, dict):
        return "No status"
    conditions: list[str] = []
    if bool(flags.get("dodging")):
        conditions.append("Dodging")
    runtime_state = flags.get("combat_runtime_state", {})
    if isinstance(runtime_state, dict):
        concentration = runtime_state.get("concentration", {})
        if isinstance(concentration, dict):
            spell_name = str(concentration.get("spell_name", "") or "").strip()
            if spell_name:
                conditions.append(f"Concentration {spell_name}")
    return " | ".join(conditions) if conditions else "No status"


def _relationship_disposition(value: int) -> str:
    score = int(value)
    if score <= -20:
        return "Hostile"
    if score >= 20:
        return "Friendly"
    return "Neutral"


def _viewport_size(ctx: LiveGameContext) -> tuple[int, int]:
    console = getattr(ctx, "ui_console", None)
    size = getattr(console, "size", None)
    width = int(getattr(size, "width", 120) or 120) if size is not None else 120
    height = int(getattr(size, "height", 40) or 40) if size is not None else 40
    return max(60, width), max(20, height)


def _density_delta(ctx: LiveGameContext) -> int:
    mode = str(getattr(ctx, "ui_density", "standard") or "standard").strip().lower()
    if mode == "compact":
        return -2
    if mode == "wide":
        return 2
    return 0


def _panel_size(ctx: LiveGameContext, *, base: int, min_size: int, max_size: int) -> int:
    _, height = _viewport_size(ctx)
    variance = (height - 40) // 10
    size = int(base) + int(variance) + _density_delta(ctx)
    return max(int(min_size), min(int(max_size), size))


def _line_budget(ctx: LiveGameContext, *, fallback: int, min_size: int, max_size: int) -> int:
    _, height = _viewport_size(ctx)
    variance = (height - 40) // 4
    budget = int(fallback) + int(variance) + (_density_delta(ctx) * 2)
    return max(int(min_size), min(int(max_size), budget))


def _cycle_density(value: str) -> str:
    current = str(value or "standard").strip().lower()
    order = ["compact", "standard", "wide"]
    if current not in order:
        return "standard"
    idx = order.index(current)
    return order[(idx + 1) % len(order)]


def _handle_density_toggle(raw: str, ctx: LiveGameContext) -> bool:
    key = str(raw or "").strip().lower()
    if key not in {"z", "density"}:
        return False
    ctx.ui_density = _cycle_density(getattr(ctx, "ui_density", "standard"))
    ctx.append_log(f"UI density set to: {str(ctx.ui_density).title()}.")
    return True


def _command_footer(ctx: LiveGameContext, *, local: str, include_back: bool, include_quit: bool) -> str:
    tokens = [f"[Z] Density:{str(getattr(ctx, 'ui_density', 'standard')).title()}", "[C] Character"]
    if include_back:
        tokens.insert(0, "[B] Back")
    if include_quit:
        tokens.append("[Q] Quit")
    return f"{local} | Global: {'  '.join(tokens)}"


def _cap_lines(lines: list[str], *, limit: int) -> list[str]:
    rows = [str(row) for row in list(lines or [])]
    safe_limit = max(1, int(limit))
    if len(rows) <= safe_limit:
        return rows
    hidden = len(rows) - safe_limit
    return [*rows[:safe_limit], f"[dim]... (+{hidden} more)[/dim]"]


def _ellipsize_plain(text: str, *, max_len: int) -> str:
    raw = str(text or "")
    if len(raw) <= max(8, int(max_len)):
        return raw
    cap = max(8, int(max_len))
    return raw[: cap - 1] + "…"


def _resolve_combat_with_tactical_hud(
    ctx: LiveGameContext,
    *,
    player: Any,
    enemies: list[Any],
    scene: dict[str, str],
) -> list[str]:
    ctx.combat_lines.append("Encounter joined.")

    def chooser(options, p, e, round_no, scene_ctx=None):
        return _choose_combat_action_live(
            ctx,
            options=options,
            player=p,
            enemy=e,
            round_no=round_no,
            scene=scene_ctx or scene,
            all_enemies=enemies,
        )

    def choose_target(actor, allies, foes, round_no, scene_ctx, action):
        _ = actor
        _ = round_no
        _ = scene_ctx
        normalized = str(action or "").strip().lower()
        if normalized in {"flee", "dash", "disengage", "dodge", "hide", "use item"}:
            return 0
        if normalized == "cast spell":
            return ("enemy", 0)
        return ("enemy", 0)

    result = ctx.game_service.combat_resolve_party_intent(
        player,
        enemies,
        chooser,
        choose_target=choose_target,
        scene=scene,
    )

    player_after = next(
        (ally for ally in list(getattr(result, "allies", []) or []) if int(getattr(ally, "id", 0) or 0) == int(getattr(player, "id", 0) or 0)),
        None,
    )
    if player_after is not None:
        ctx.game_service.save_character_state(player_after)

    log_lines = [str(getattr(entry, "text", "") or "").strip() for entry in list(getattr(result, "log", []) or [])]
    for row in [line for line in log_lines if line]:
        ctx.combat_lines.append(row)
        ctx.append_log(row)

    resolution: list[str] = []
    if bool(getattr(result, "fled", False)):
        resolution.append("You escaped the encounter.")
        retreat = ctx.game_service.apply_retreat_consequence_intent(ctx.character_id)
        resolution.extend(list(getattr(retreat, "messages", []) or []))
    elif bool(getattr(result, "allies_won", False)):
        resolution.append("Your party survives the encounter.")
    else:
        defeat = ctx.game_service.apply_defeat_consequence_intent(ctx.character_id)
        resolution.extend(list(getattr(defeat, "messages", []) or ["Defeat consequence applied."]))

    for line in resolution:
        ctx.append_log(str(line))
    _queue_narrative_task(ctx, "combat", "Inscribing battle chronicle")
    return [line for line in resolution if str(line).strip()]


def _choose_combat_action_live(
    ctx: LiveGameContext,
    *,
    options: list[str],
    player: Any,
    enemy: Any,
    round_no: int,
    scene: dict[str, str],
    all_enemies: list[Any],
):
    round_view = ctx.game_service.combat_round_view_intent(
        options=options,
        player=player,
        enemy=enemy,
        round_no=round_no,
        scene_ctx=scene,
    )

    header, world_summary = _build_header_lines(ctx)
    if ctx.ui_live is not None:
        ctx.ui_live.update(
            _render_tactical_hud_layout(
                header=header,
                world_summary=world_summary,
                player=player,
                enemies=all_enemies,
                scene=scene,
                recent_lines=list(ctx.combat_lines),
                options=list(round_view.options),
                title=f"Tactical Combat HUD — Round {round_no}",
                footer="Choose action by number (or press ENTER to Dodge).",
            )
        )

    console = ctx.ui_console
    if console is None:
        selected_index = 0
    else:
        raw = console.input("[bold cyan]Combat Action[/bold cyan] > ").strip().lower()
        if not raw:
            selected_index = -1
        elif raw.isdigit():
            selected_index = int(raw) - 1
        else:
            try:
                selected_index = next(i for i, row in enumerate(round_view.options) if str(row).strip().lower() == raw)
            except StopIteration:
                selected_index = -1

    selected = round_view.options[selected_index] if 0 <= selected_index < len(round_view.options) else "Dodge"
    spell_slug = None
    cast_level = None
    use_ritual = False
    item_name = None
    if selected == "Cast Spell":
        spell_slug, cast_level, use_ritual = _choose_spell_live(ctx, player)
    if selected == "Use Item":
        item_name = _choose_item_live(ctx, player)

    decision = ctx.game_service.submit_combat_action_intent(
        options=list(round_view.options),
        selected_index=selected_index,
        spell_slug=spell_slug,
        cast_level=cast_level,
        use_ritual=use_ritual,
        item_name=item_name,
    )
    ctx.combat_lines.append(f"Round {round_no}: {str(selected)}")
    return decision


def _choose_spell_live(ctx: LiveGameContext, player: Any) -> tuple[str | None, int | None, bool]:
    options = list(ctx.game_service.list_spell_options(player) or [])
    if not options:
        ctx.combat_lines.append("No spells available.")
        return None, None, False
    console = ctx.ui_console
    if console is None:
        first = options[0]
        levels = list(getattr(first, "cast_levels", []) or [])
        return str(getattr(first, "slug", "") or ""), (levels[0] if levels else None), False
    rows = [f"[{i}] {getattr(row, 'label', '')}" for i, row in enumerate(options, start=1)]
    prompt = "\n".join(["Cast Spell:", *rows, "Enter number or press ENTER to cancel"]) + "\n"
    raw = console.input(prompt).strip()
    if not raw or not raw.isdigit():
        return None, None, False
    idx = int(raw) - 1
    if idx < 0 or idx >= len(options):
        return None, None, False

    selected = options[idx]
    slug = str(getattr(selected, "slug", "") or "") or None
    cast_levels = [int(row) for row in list(getattr(selected, "cast_levels", []) or []) if int(row) > 0]
    chosen_level = None
    if cast_levels:
        if len(cast_levels) == 1:
            chosen_level = cast_levels[0]
        else:
            level_prompt = "\n".join(
                [
                    f"Cast level options: {', '.join(str(row) for row in cast_levels)}",
                    "Enter level (or press ENTER for minimum):",
                ]
            ) + "\n"
            level_raw = console.input(level_prompt).strip()
            if level_raw.isdigit() and int(level_raw) in cast_levels:
                chosen_level = int(level_raw)
            else:
                chosen_level = cast_levels[0]

    ritual = False
    is_ritual = bool(getattr(selected, "ritual", False))
    if is_ritual:
        ritual_raw = console.input("Cast as ritual? [y/N] > ").strip().lower()
        ritual = ritual_raw in {"y", "yes"}

    return slug, chosen_level, ritual


def _choose_item_live(ctx: LiveGameContext, player: Any) -> str | None:
    options = list(ctx.game_service.list_combat_item_options(player) or [])
    if not options:
        ctx.combat_lines.append("No combat items available.")
        return None
    console = ctx.ui_console
    if console is None:
        return str(options[0])
    rows = [f"[{i}] {row}" for i, row in enumerate(options, start=1)]
    prompt = "\n".join(["Use Item:", *rows, "Enter number or press ENTER to cancel"]) + "\n"
    raw = console.input(prompt).strip()
    if not raw or not raw.isdigit():
        return None
    idx = int(raw) - 1
    if idx < 0 or idx >= len(options):
        return None
    return str(options[idx])


def _handle_world_spellcast(ctx: LiveGameContext) -> GameState:
    player = _safe_player_character(ctx)
    if player is None:
        ctx.append_log("Cannot access character spell data right now.")
        return ExplorationState()

    try:
        options = list(ctx.game_service.list_spell_options(player) or [])
    except Exception as exc:
        ctx.append_log(f"Spell list unavailable: {exc}")
        return ExplorationState()

    playable = [row for row in options if bool(getattr(row, "playable", False))]
    if not playable:
        ctx.append_log("No world-castable spells available.")
        return ExplorationState()

    selected = playable[0]
    console = ctx.ui_console
    if console is not None:
        rows = [f"[{idx}] {getattr(row, 'label', '')}" for idx, row in enumerate(playable, start=1)]
        raw = console.input("\n".join(["Cast Spell (World):", *rows, "Enter number or press ENTER to cancel"]) + "\n").strip()
        if not raw:
            ctx.append_log("World spellcast canceled.")
            return ExplorationState()
        if not raw.isdigit():
            ctx.append_log("Invalid spell selection.")
            return ExplorationState()
        idx = int(raw) - 1
        if idx < 0 or idx >= len(playable):
            ctx.append_log("Spell selection out of range.")
            return ExplorationState()
        selected = playable[idx]

    spell_slug = str(getattr(selected, "slug", "") or "").strip().lower()
    if not spell_slug:
        ctx.append_log("Selected spell is invalid.")
        return ExplorationState()

    cast_level = None
    cast_levels = [int(level) for level in list(getattr(selected, "cast_levels", []) or []) if int(level) > 0]
    if cast_levels:
        cast_level = cast_levels[0]
        if console is not None and len(cast_levels) > 1:
            level_raw = console.input(
                "\n".join(
                    [
                        f"Cast level options: {', '.join(str(level) for level in cast_levels)}",
                        "Enter cast level (or press ENTER for minimum)",
                    ]
                )
                + "\n"
            ).strip()
            if level_raw.isdigit() and int(level_raw) in cast_levels:
                cast_level = int(level_raw)

    as_ritual = False
    if bool(getattr(selected, "ritual", False)):
        if console is not None:
            ritual_raw = console.input("Cast as ritual (+10 minutes)? [y/N] > ").strip().lower()
            as_ritual = ritual_raw in {"y", "yes"}

    try:
        result = ctx.game_service.cast_world_spell_intent(
            ctx.character_id,
            spell_slug,
            cast_level=cast_level,
            as_ritual=as_ritual,
        )
        for line in list(getattr(result, "messages", []) or []):
            msg = str(line)
            ctx.append_log(msg)
            ctx.exploration_lines.append(msg)
    except Exception as exc:
        ctx.append_log(f"World spellcast failed: {exc}")
        return ExplorationState()

    _queue_narrative_task(ctx, "spellcast", "Annotating spellcasting entry")
    return ExplorationState()


def _handle_explore_step(ctx: LiveGameContext) -> GameState:
    try:
        explore_view, character, enemies = ctx.game_service.explore_intent(ctx.character_id)
    except Exception as exc:
        ctx.append_log(f"Explore failed: {exc}")
        return ExplorationState()

    message = str(getattr(explore_view, "message", "You scout the area.") or "You scout the area.")
    ctx.append_log(message)
    ctx.exploration_lines.append(message)

    if not enemies:
        return ExplorationState()

    scene = {
        "distance": random.choice(["close", "mid", "far"]),
        "surprise": random.choice(["none", "player", "enemy"]),
        "terrain": random.choice(["open", "cramped", "difficult"]),
    }
    loop_view = ctx.game_service.get_game_loop_view(ctx.character_id)
    weather_label = str(getattr(loop_view, "weather_label", "") or "").strip()
    if weather_label:
        scene["weather"] = weather_label

    surprise_override = ctx.game_service.consume_next_explore_surprise_intent(ctx.character_id)
    if surprise_override:
        scene["surprise"] = str(surprise_override)

    hostiles = ", ".join(f"{getattr(enemy, 'name', 'Enemy')} ({getattr(enemy, 'hp_current', 0)}/{getattr(enemy, 'hp_max', 0)})" for enemy in enemies)
    intro = f"Hostiles sighted: {hostiles}."
    ctx.append_log(intro)
    ctx.exploration_lines.append(intro)
    return CombatState(character, enemies, scene, return_state=ExplorationState())


def _queue_narrative_task(ctx: LiveGameContext, event_kind: str, label: str) -> None:
    queue = ctx.event_queue
    if queue is None:
        return
    queue.publish(event_kind=event_kind, payload={"character_id": ctx.character_id}, label=label)


def _build_header_lines(ctx: LiveGameContext) -> tuple[str, str]:
    try:
        view = ctx.game_service.get_game_loop_view(ctx.character_id)
        location_context = ctx.game_service.get_location_context_intent(ctx.character_id)
    except Exception:
        return "Character unavailable", "No world snapshot available."

    race = str(getattr(view, "race", "") or "").strip()
    class_name = str(getattr(view, "class_name", "") or "").strip().title()
    descriptor = " ".join(row for row in [race, class_name] if row) or "Adventurer"
    name = str(getattr(view, "name", "Adventurer") or "Adventurer")
    hp = f"{getattr(view, 'hp_current', '?')}/{getattr(view, 'hp_max', '?')}"
    location_name = str(getattr(location_context, "current_location_name", "Unknown") or "Unknown")

    world_turn = getattr(view, "world_turn", None)
    day = f"Day {world_turn}" if world_turn is not None else "Day ?"
    weather = str(getattr(view, "weather_label", "Unknown") or "Unknown")
    time_label = str(getattr(view, "time_label", "Time Unknown") or "Time Unknown")

    header = f"Name: {name} ({descriptor}) | HP: {hp} | Location: {location_name}"
    world = f"{day} | {time_label} | Weather: {weather}"
    return header, world


def _handle_act(ctx: LiveGameContext) -> GameState:
    try:
        location_context = ctx.game_service.get_location_context_intent(ctx.character_id)
        if str(getattr(location_context, "location_type", "")) == "town":
            legacy_loop._run_town(ctx.game_service, ctx.character_id)
            ctx.append_log("Town actions complete.")
        else:
            legacy_loop._run_explore(ctx.game_service, ctx.character_id)
            ctx.append_log("Exploration action complete.")
        _queue_narrative_task(ctx, "act", "Compiling encounter flavour")
    except Exception as exc:
        ctx.append_log(f"Act flow failed: {exc}")
    return RootState()


def _deferred_narrative_handler(event: DeferredEvent) -> str:
    time.sleep(0.12)
    kind = str(event.kind).replace("_", " ")
    return f"Narrative update finished for: {kind}."


def run_live_game_loop(game_service: Any, character_id: int) -> None:
    """Opt-in Rich Live+FSM gameplay loop with deferred side-effect queue."""

    if Console is None or Live is None or Layout is None or Panel is None:
        legacy_loop.run_game_loop(game_service, character_id)
        return

    console = Console()
    ctx = LiveGameContext(game_service=game_service, character_id=int(character_id))
    ctx.append_log("Live FSM mode active.")

    queue = AsyncEventQueue(on_message=ctx.append_log)
    queue.register_handler("*", _deferred_narrative_handler)
    queue.start()
    ctx.event_queue = queue

    state: GameState = RootState()

    try:
        with Live(state.render(ctx), console=console, refresh_per_second=8, screen=True) as live:
            ctx.ui_console = console
            ctx.ui_live = live
            while not ctx.should_exit:
                live.update(state.render(ctx))
                user_input = console.input("[bold cyan]Action[/bold cyan] > ").strip()
                state = state.handle_input(user_input, ctx)
                live.update(state.render(ctx))
    except KeyboardInterrupt:
        pass
    finally:
        ctx.ui_live = None
        ctx.ui_console = None
        queue.stop()
