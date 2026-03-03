import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict

from rpg.application.services.character_creation_service import ABILITY_ORDER
from rpg.presentation.menu_controls import arrow_menu, clear_screen, read_key, normalize_menu_key
from rpg.presentation.rolling_ui import roll_attributes_with_animation, ATTR_ORDER

try:
    from rich.layout import Layout
    from rich.console import Console
    from rich.columns import Columns
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
except Exception:  # pragma: no cover - optional dependency fallback
    Layout = None
    Console = None
    Columns = None
    Live = None
    Panel = None
    Table = None


_CONSOLE = Console() if Console is not None else None
_CREATION_HELP_HINT = "Need guidance? Open the Creation Library."
_PANEL_BORDER = "cyan"
_THEME = {
    "title": "bold yellow",
    "attributes": "bold cyan",
    "class_race": "bold magenta",
    "warning": "bold red",
    "success": "bold green",
    "muted": "white",
}

_RACE_AUTO_LANGUAGES = {
    "human": ["Common"],
    "elf": ["Common", "Elvish"],
    "half elf": ["Common", "Elvish"],
    "half-elf": ["Common", "Elvish"],
    "dwarf": ["Common", "Dwarvish"],
    "halfling": ["Common", "Halfling"],
    "half orc": ["Common", "Orc"],
    "half-orc": ["Common", "Orc"],
    "orc": ["Common", "Orc"],
    "tiefling": ["Common", "Infernal"],
    "dragonborn": ["Common", "Draconic"],
    "dark elf": ["Common", "Elvish", "Undercommon"],
}


@dataclass
class CreationDraft:
    name: str = ""
    name_gender: str = ""
    race: str = ""
    subrace: str = ""
    class_name: str = ""
    subclass_name: str = ""
    ability_scores: Dict[str, int] = field(default_factory=dict)
    background: str = ""
    difficulty: str = ""
    alignment: str = ""
    equipment: str = ""
    spells: str = ""
    show_detailed: bool = False
    auto_languages: list[str] = field(default_factory=list)
    chosen_languages: list[str] = field(default_factory=list)
    chosen_tools: list[str] = field(default_factory=list)
    racial_traits: list[str] = field(default_factory=list)
    progress_steps: list[str] = field(default_factory=list)
    progress_index: int = 0


def _normalize_label_token(value: str | None) -> str:
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").strip().lower().split())


def _race_auto_languages(race_name: str | None, subrace_name: str | None = None) -> list[str]:
    keys = [
        _normalize_label_token(subrace_name),
        _normalize_label_token(race_name),
    ]
    for key in keys:
        if not key:
            continue
        rows = _RACE_AUTO_LANGUAGES.get(key)
        if rows:
            return [str(row) for row in rows if str(row).strip()]
    return []


def _compact_rows(rows: list[str], limit: int = 6) -> str:
    clean = [str(row) for row in list(rows or []) if str(row).strip()]
    if not clean:
        return "—"
    if len(clean) <= limit:
        return ", ".join(clean)
    hidden = len(clean) - limit
    return f"{', '.join(clean[:limit])} (+{hidden} more)"


def _progress_markup(draft: CreationDraft) -> str:
    steps = [str(row) for row in list(getattr(draft, "progress_steps", []) or []) if str(row).strip()]
    if not steps:
        return ""
    current = int(getattr(draft, "progress_index", 0) or 0)
    nodes: list[str] = []
    for idx, label in enumerate(steps):
        if idx < current:
            nodes.append(f"[{_THEME['success']}]✔ {label}[/{_THEME['success']}]")
        elif idx == current:
            nodes.append(f"[bold yellow]● {label}[/bold yellow]")
        else:
            nodes.append(f"[{_THEME['muted']}]{label}[/{_THEME['muted']}]")
    return " ❯ ".join(nodes)


def _draft_lines(draft: CreationDraft) -> list[str]:
    race_line = draft.race or "???"
    if draft.subrace:
        race_line = f"{race_line} ({draft.subrace})"
    gender_value = str(getattr(draft, "name_gender", "") or "").strip().lower()
    if gender_value in {"male", "female", "random"}:
        gender_label = gender_value.title()
    else:
        gender_label = "???"
    ability_line = " / ".join(
        f"{abbr} {int(draft.ability_scores.get(abbr, 8))}" for abbr in ABILITY_ORDER
    ) if draft.ability_scores else "Not assigned"
    lines = [
        f"Name: {draft.name or '???'}",
        f"Gender: {gender_label}",
        f"Race: {race_line}",
        f"Class: {draft.class_name or '???'}",
        f"Subclass: {draft.subclass_name or '—'}",
        f"Background: {draft.background or '???'}",
        f"Difficulty: {draft.difficulty or '???'}",
        f"Alignment: {draft.alignment or '???'}",
        f"Equipment: {draft.equipment or '???'}",
        f"Spells: {draft.spells or '—'}",
        "",
        f"Stats: {ability_line}",
    ]
    if bool(getattr(draft, "show_detailed", False)):
        lines.extend(
            [
                "",
                "[bold cyan]Details[/bold cyan]",
                f"Auto Languages: {_compact_rows(list(getattr(draft, 'auto_languages', []) or []), limit=8)}",
                f"Chosen Languages: {_compact_rows(list(getattr(draft, 'chosen_languages', []) or []), limit=8)}",
                f"Tools: {_compact_rows(list(getattr(draft, 'chosen_tools', []) or []), limit=8)}",
                f"Racial Traits: {_compact_rows(list(getattr(draft, 'racial_traits', []) or []), limit=6)}",
            ]
        )
    return lines


def _draft_panel(draft: CreationDraft):
    lines = _draft_lines(draft)
    if Panel is None:
        return "\n".join(lines)
    return Panel.fit(
        "\n".join(lines),
        title="[bold yellow]Character Draft[/bold yellow]",
        border_style=_PANEL_BORDER,
    )


def _creation_split_view(
    title: str,
    body_lines: list[str],
    draft: CreationDraft,
    *,
    footer_hint: str = "",
    context_title: str = "Context",
    context_lines: list[str] | None = None,
):
    if Panel is None or Columns is None:
        return "\n".join(body_lines)
    left_lines = list(body_lines)
    if footer_hint:
        left_lines.append("")
        left_lines.append(f"[yellow]{footer_hint}[/yellow]")
    left_lines.append("[bold cyan]V[/bold cyan] Toggle draft details")
    left_lines.append("[bold white]Use arrow keys to move, ENTER to select, ESC to go back.[/bold white]")
    left_panel = Panel.fit(
        "\n".join(left_lines),
        title=f"[{_THEME['title']}]{title}[/{_THEME['title']}]",
        border_style=_PANEL_BORDER,
    )

    context_rows = [str(row) for row in list(context_lines or []) if str(row).strip()]
    if not context_rows:
        context_rows = ["Hover options to inspect lore and mechanics."]
    context_panel = Panel.fit(
        "\n".join(context_rows),
        title=f"[{_THEME['class_race']}]{context_title}[/{_THEME['class_race']}]",
        border_style="magenta",
    )

    progress_line = _progress_markup(draft)
    if Layout is not None:
        layout = Layout(name="creation")
        layout.split_column(
            Layout(name="progress", size=3),
            Layout(name="upper", ratio=2),
            Layout(name="context", size=max(6, min(12, len(context_rows) + 3))),
        )
        layout["upper"].split_row(Layout(name="menu"), Layout(name="draft"))
        layout["menu"].update(left_panel)
        layout["draft"].update(_draft_panel(draft))
        layout["context"].update(context_panel)
        layout["progress"].update(
            Panel.fit(
                progress_line or "[bold white]Character creation in progress...[/bold white]",
                border_style="cyan",
            )
        )
        return layout

    return Columns([left_panel, _draft_panel(draft)], expand=True, equal=True)


def _creation_menu(
    title: str,
    options: list[str],
    draft: CreationDraft,
    *,
    footer_hint: str | None = None,
    context_provider: Callable[[int], tuple[str, list[str]] | None] | None = None,
    quick_keys: dict[str, int] | None = None,
) -> int:
    if _CONSOLE is None or Panel is None or Columns is None or Live is None:
        return arrow_menu(title, options, footer_hint=footer_hint)

    selected = 0
    window_size = 10

    def _window_bounds() -> tuple[int, int]:
        total = len(options)
        if total <= window_size:
            return 0, total
        half = window_size // 2
        start = max(0, selected - half)
        end = min(total, start + window_size)
        if (end - start) < window_size:
            start = max(0, end - window_size)
        return start, end

    def _body_lines() -> list[str]:
        rows = []
        start, end = _window_bounds()
        if start > 0:
            rows.append("[dim]↑ more options above[/dim]")
        for idx in range(start, end):
            option = options[idx]
            if idx == selected:
                rows.append(f"[bold black on bright_cyan] ▶ {option} [/bold black on bright_cyan]")
            else:
                rows.append(f"[white]  {option}[/white]")
        if end < len(options):
            rows.append("[dim]↓ more options below[/dim]")
        rows.append("")
        rows.append(f"[dim]Showing {start + 1}-{end} of {len(options)}[/dim]")
        return rows

    def _context_payload() -> tuple[str, list[str]]:
        if context_provider is None:
            return "Context", []
        payload = context_provider(selected)
        if payload is None:
            return "Context", []
        panel_title, panel_rows = payload
        return str(panel_title or "Context"), [str(row) for row in list(panel_rows or [])]

    def _render_view():
        context_title, context_lines = _context_payload()
        return _creation_split_view(
            title,
            _body_lines(),
            draft,
            footer_hint=str(footer_hint or ""),
            context_title=context_title,
            context_lines=context_lines,
        )

    clear_screen()
    with Live(
        _render_view(),
        console=_CONSOLE,
        refresh_per_second=24,
        transient=True,
    ) as live:
        while True:
            raw_key = read_key()
            key = normalize_menu_key(raw_key)
            raw = str(raw_key or "").strip().lower()
            if raw == "v":
                draft.show_detailed = not bool(getattr(draft, "show_detailed", False))
                live.update(_render_view(), refresh=True)
                continue
            if key == "UP":
                selected = (selected - 1) % len(options)
                live.update(_render_view(), refresh=True)
                continue
            if key == "DOWN":
                selected = (selected + 1) % len(options)
                live.update(_render_view(), refresh=True)
                continue
            if quick_keys and raw in quick_keys:
                mapped = int(quick_keys.get(raw, -1))
                if 0 <= mapped < len(options):
                    return mapped
            if key == "ENTER":
                return selected
            if key == "ESC":
                return -1


def _prompt_enter(message: str = "Press ENTER to continue...") -> None:
    if _CONSOLE is not None:
        _CONSOLE.input(f"[bold white]{message}[/bold white]")
        clear_screen()
        return
    input(message)
    clear_screen()


def _prompt_custom_name(draft: CreationDraft | None = None) -> str:
    clear_screen()
    if _CONSOLE is not None and Panel is not None and Columns is not None and draft is not None:
        left = Panel.fit(
            "\n".join(
                [
                    "Enter your character's name (max 20 chars, leave blank for generated).",
                    "Type [bold]help[/bold] to open the creation help library.",
                    "Type [bold]esc[/bold] to go back.",
                ]
            ),
            title="[bold yellow]Character Creation[/bold yellow]",
            border_style=_PANEL_BORDER,
        )
        _CONSOLE.print(Columns([left, _draft_panel(draft)], expand=True, equal=True))
        return _CONSOLE.input("[bold yellow]>>> [/bold yellow]")

    if _CONSOLE is not None and Panel is not None:
        _CONSOLE.print(
            Panel.fit(
                "\n".join(
                    [
                        "Enter your character's name (max 20 chars, leave blank for generated).",
                        "Type [bold]help[/bold] to open the creation help library.",
                        "Type [bold]esc[/bold] to go back.",
                    ]
                ),
                title="[bold yellow]Character Creation[/bold yellow]",
                border_style=_PANEL_BORDER,
            )
        )
        return _CONSOLE.input("[bold yellow]>>> [/bold yellow]")

    print("=" * 40)
    print(f"{'Character Creation':^40}")
    print("=" * 40)
    print("")
    print("Enter your character's name (max 20 chars, leave blank for generated):")
    print("Type 'help' to open the creation help library.")
    print("Type 'esc' to go back.")
    print(">>> ", end="")
    return input()


def _choose_name(creation_service, draft: CreationDraft):
    def _resolve_generated_name() -> str:
        class_index = 0
        class_name = str(getattr(draft, "class_name", "") or "").strip().lower()
        if class_name:
            for index, label in enumerate(list(creation_service.list_class_names() or [])):
                if str(label or "").strip().lower() == class_name:
                    class_index = int(index)
                    break
        current_gender = str(getattr(draft, "name_gender", "random") or "random").strip().lower()
        return creation_service.suggest_generated_name(
            race_name=str(getattr(draft, "race", "") or "").strip() or None,
            class_index=class_index,
            gender=current_gender if current_gender in {"male", "female", "nonbinary"} else None,
        )

    while True:
        current_gender = str(getattr(draft, "name_gender", "random") or "random").strip().lower()
        if current_gender not in {"male", "female", "nonbinary", "random"}:
            current_gender = "random"

        options = [
            "Enter custom name",
            "Use generated name",
            "Reroll generated name",
            "Help: Creation Reference Library",
            "Cancel character creation",
        ]
        idx = _creation_menu(
            "Character Creation",
            options,
            draft,
            footer_hint="ESC to return to main menu. Press [bold cyan]R[/bold cyan] to reroll generated name.",
            quick_keys={"r": 2},
        )
        if idx < 0 or idx == 4:
            return False, ""
        if idx == 3:
            _show_creation_reference_library(creation_service)
            continue
        if idx == 2:
            generated_name = _resolve_generated_name()
            draft.name = str(generated_name or "")
            continue
        if idx == 1:
            generated_name = _resolve_generated_name()
            return True, generated_name

        raw_name = _prompt_custom_name(draft)
        lowered = (raw_name or "").strip().lower()
        if lowered in {"help", "?"}:
            _show_creation_reference_library(creation_service)
            continue
        if lowered in {"esc", "cancel", "q", "quit"}:
            continue
        return True, raw_name


def _choose_name_generation_gender(draft: CreationDraft) -> str | None:
    options = ["Random", "Male", "Female", "Non-Binary"]
    idx = _creation_menu(
        "Gender",
        options,
        draft,
        footer_hint="This affects generated names only. Custom names ignore this setting.",
    )
    if idx < 0:
        return None
    return ["random", "male", "female", "nonbinary"][idx]


def _render_character_summary(summary) -> None:
    if _CONSOLE is not None and Panel is not None and Columns is not None and Table is not None:
        class_line = f"Level {summary.level} {summary.class_name}"
        if getattr(summary, "subclass_name", ""):
            class_line += f" ({summary.subclass_name})"

        headline = Panel.fit(
            f"[bold yellow]THE CHRONICLE OF {str(summary.name).upper()}[/bold yellow]",
            border_style=_PANEL_BORDER,
        )

        top_meta = Table.grid(expand=True)
        top_meta.add_column(justify="left")
        top_meta.add_column(justify="left")
        top_meta.add_row(
            f"[{_THEME['class_race']}]Race[/{_THEME['class_race']}]: {summary.race}",
            f"Alignment: {summary.alignment}",
        )
        top_meta.add_row(
            f"[{_THEME['class_race']}]Background[/{_THEME['class_race']}]: {summary.background}",
            f"Difficulty: {summary.difficulty}",
        )
        top_meta.add_row(class_line, f"Starting Location: {summary.starting_location_name}")

        attr_table = Table(show_header=False, box=None, expand=True)
        attr_table.add_column()
        attr_table.add_column(justify="right")
        for token in [part.strip() for part in str(summary.attributes_line or "").split("/") if part.strip()]:
            parts = token.split()
            if len(parts) < 2:
                continue
            stat = str(parts[0]).upper()
            try:
                score = int(parts[1])
            except Exception:
                continue
            mod = (score - 10) // 2
            mod_sign = f"+{mod}" if mod >= 0 else str(mod)
            attr_table.add_row(f"[{_THEME['attributes']}]{stat}[/{_THEME['attributes']}]", f"{score} ({mod_sign})")

        combat_table = Table(show_header=False, box=None, expand=True)
        combat_table.add_column()
        combat_table.add_column(justify="right")
        combat_table.add_row("Max HP", f"{summary.hp_max}")
        combat_table.add_row("Current HP", f"{summary.hp_current}")
        combat_table.add_row("Speed", f"{summary.speed} ft")
        combat_table.add_row("Gear Items", f"{len(list(summary.inventory or []))}")

        left_block = Panel.fit(attr_table, title="[bold cyan]Attributes[/bold cyan]", border_style="cyan")
        right_block = Panel.fit(combat_table, title="[bold green]Core Stats[/bold green]", border_style="green")

        picks_table = Table(show_header=False, box=None, expand=True)
        picks_table.add_column(width=20)
        picks_table.add_column()
        tools = [str(row) for row in list(getattr(summary, "tool_proficiencies", []) or []) if str(row).strip()]
        languages = [str(row) for row in list(getattr(summary, "languages", []) or []) if str(row).strip()]
        features = [str(row) for row in list(getattr(summary, "class_feature_summary", []) or []) if str(row).strip()]
        picks_table.add_row("Tools", ", ".join(tools) if tools else "—")
        picks_table.add_row("Languages", ", ".join(languages) if languages else "—")
        picks_table.add_row("Trait", str(getattr(summary, "personality_trait", "") or "—"))
        picks_table.add_row("Ideal", str(getattr(summary, "personality_ideal", "") or "—"))
        picks_table.add_row("Bond", str(getattr(summary, "personality_bond", "") or "—"))
        picks_table.add_row("Flaw", str(getattr(summary, "personality_flaw", "") or "—"))
        picks_table.add_row("Class Features", ", ".join(features) if features else "—")
        picks_table.add_row("Feat", str(getattr(summary, "feat_name", "") or "—"))

        gear_text = ", ".join(list(summary.inventory or [])) if list(summary.inventory or []) else "—"
        gear_panel = Panel.fit(gear_text, title="[bold yellow]Starting Equipment[/bold yellow]", border_style="cyan")

        _CONSOLE.print(headline)
        _CONSOLE.print(top_meta)
        _CONSOLE.print(Columns([left_block, right_block], expand=True, equal=True))
        _CONSOLE.print(Panel.fit(picks_table, title="[bold magenta]Narrative & Mechanical Picks[/bold magenta]", border_style="magenta"))
        _CONSOLE.print(gear_panel)
        return

    print(f"You created: {summary.name}, a level {summary.level} {summary.class_name}.")
    if getattr(summary, "subclass_name", ""):
        print(f"Subclass: {summary.subclass_name}")
    print(f"Alignment: {summary.alignment}")
    print(f"Race: {summary.race} (Speed {summary.speed})")
    print(f"Background: {summary.background}")
    print(f"Difficulty: {summary.difficulty}")
    print(f"HP: {summary.hp_current}/{summary.hp_max}")
    print(f"Abilities: {summary.attributes_line}")
    if summary.race_traits:
        print(f"Race Traits: {', '.join(summary.race_traits)}")
    if summary.background_features:
        print(f"Background Feature: {', '.join(summary.background_features)}")
    if summary.inventory:
        print(f"Starting Gear: {', '.join(summary.inventory)}")
    print("")
    print("Narrative & Mechanical Picks:")
    tool_rows = [str(row) for row in list(getattr(summary, "tool_proficiencies", []) or []) if str(row).strip()]
    language_rows = [str(row) for row in list(getattr(summary, "languages", []) or []) if str(row).strip()]
    print(f"Tools: {', '.join(tool_rows) if tool_rows else '—'}")
    print(f"Languages: {', '.join(language_rows) if language_rows else '—'}")

    trait = str(getattr(summary, "personality_trait", "") or "").strip()
    ideal = str(getattr(summary, "personality_ideal", "") or "").strip()
    bond = str(getattr(summary, "personality_bond", "") or "").strip()
    flaw = str(getattr(summary, "personality_flaw", "") or "").strip()
    if any([trait, ideal, bond, flaw]):
        print(f"Trait: {trait or '—'}")
        print(f"Ideal: {ideal or '—'}")
        print(f"Bond: {bond or '—'}")
        print(f"Flaw: {flaw or '—'}")
    else:
        print("Personality Profile: —")

    feature_rows = [str(row) for row in list(getattr(summary, "class_feature_summary", []) or []) if str(row).strip()]
    print(f"Class Features: {', '.join(feature_rows) if feature_rows else '—'}")

    feat_name = str(getattr(summary, "feat_name", "") or "").strip()
    print(f"Feat: {feat_name or '—'}")
    print(f"Starting Location: {summary.starting_location_name}")


def _show_class_detail(creation_service, chosen_class, draft: CreationDraft) -> bool:
    """Return True if player confirms the class (arrow-key driven)."""
    detail = creation_service.class_detail_view(chosen_class)
    options = detail.options
    selected = 0

    while True:
        clear_screen()
        if _CONSOLE is not None and Panel is not None and Columns is not None:
            lines = [
                detail.description,
                "",
                f"[{_THEME['attributes']}]Primary Ability[/{_THEME['attributes']}] : {detail.primary_ability}",
                f"[{_THEME['attributes']}]Hit Die[/{_THEME['attributes']}]         : {detail.hit_die}",
                f"Combat Profile  : {detail.combat_profile_line}",
            ]
            if detail.recommended_line:
                lines.append(f"Recommended     : {detail.recommended_line}")
            progression_rows = list(getattr(detail, "progression_rows", []) or [])
            if progression_rows:
                lines.append("")
                lines.append(f"[{_THEME['attributes']}]Class Progression (1–20)[/{_THEME['attributes']}]")
                lines.append("Level | Gains")
                lines.append("------|------------------------------------------------")
                for row in progression_rows:
                    gains = str(getattr(row, "gains", "") or "").strip() or "—"
                    level = int(getattr(row, "level", 0) or 0)
                    lines.append(f"{level:>5} | {gains}")
            lines.append("")
            for idx, opt in enumerate(options):
                if idx == selected:
                    lines.append(f"[bold black on bright_cyan] ▶ {opt} [/bold black on bright_cyan]")
                else:
                    lines.append(f"[white]  {opt}[/white]")
            lines.append("")
            lines.append(f"[yellow]{_CREATION_HELP_HINT}[/yellow]")
            lines.append("[bold white]Use arrow keys to move, ENTER to select, ESC to cancel.[/bold white]")
            _CONSOLE.print(
                Columns(
                    [
                        Panel.fit(
                            "\n".join(lines),
                            title=f"[{_THEME['class_race']}]{detail.title}[/{_THEME['class_race']}]",
                            border_style=_PANEL_BORDER,
                            subtitle="[bold white]↑/↓ Navigate • Enter Confirm • Esc Back[/bold white]",
                            subtitle_align="left",
                        ),
                        _draft_panel(draft),
                    ],
                    expand=True,
                    equal=True,
                )
            )
        else:
            print("=" * 40)
            print(f"{detail.title:^40}")
            print("=" * 40)
            print(detail.description)
            print("")
            print(f"Primary Ability : {detail.primary_ability}")
            print(f"Hit Die         : {detail.hit_die}")
            print(f"Combat Profile  : {detail.combat_profile_line}")
            if detail.recommended_line:
                print(f"Recommended     : {detail.recommended_line}")
            progression_rows = list(getattr(detail, "progression_rows", []) or [])
            if progression_rows:
                print("")
                print("Class Progression (1–20)")
                print("Level | Gains")
                print("------|------------------------------------------------")
                for row in progression_rows:
                    gains = str(getattr(row, "gains", "") or "").strip() or "—"
                    level = int(getattr(row, "level", 0) or 0)
                    print(f"{level:>5} | {gains}")
            print("")
            for idx, opt in enumerate(options):
                prefix = "> " if idx == selected else "  "
                print(f"{prefix}{opt}")
            print("")
            print(_CREATION_HELP_HINT)
            print("-" * 40)
            print("Use arrow keys to move, ENTER to select, ESC to cancel.")
            print("-" * 40)

        key = normalize_menu_key(read_key())
        if key == "UP":
            selected = (selected - 1) % len(options)
        elif key == "DOWN":
            selected = (selected + 1) % len(options)
        elif key == "ENTER":
            return selected == 0
        elif key == "ESC":
            return False


def _choose_race(creation_service, draft: CreationDraft):
    races = creation_service.list_playable_races()

    def _race_option_line(race) -> str:
        name = str(getattr(race, "name", "Race") or "Race")
        speed = int(getattr(race, "speed", 30) or 30)
        bonuses = creation_service._format_bonus_line(getattr(race, "bonuses", {}) or {})
        return f"{name:<12} | {bonuses:<16} | {speed:>2} ft"

    def _context_for(index: int) -> tuple[str, list[str]]:
        if index >= len(races):
            return "Creation Library", ["Open the reference library to browse races and lore."]
        race = races[index]
        traits = [str(row) for row in list(getattr(race, "traits", []) or []) if str(row).strip()]
        return (
            str(getattr(race, "name", "Race") or "Race"),
            [
                f"[{_THEME['class_race']}]Speed[/{_THEME['class_race']}]: {int(getattr(race, 'speed', 30) or 30)} ft",
                f"[{_THEME['attributes']}]Bonuses[/{_THEME['attributes']}]: {creation_service._format_bonus_line(getattr(race, 'bonuses', {}) or {})}",
                f"Traits: {', '.join(traits) if traits else 'None listed'}",
            ],
        )

    while True:
        options = [_race_option_line(row) for row in races] + ["Help: Creation Reference Library"]
        idx = _creation_menu(
            "Choose Your Race",
            options,
            draft,
            footer_hint=_CREATION_HELP_HINT,
            context_provider=_context_for,
        )
        if idx < 0:
            return None
        if idx == len(options) - 1:
            _show_creation_reference_library(creation_service)
            continue
        return races[idx]


def _choose_background(creation_service, draft: CreationDraft):
    backgrounds = creation_service.list_backgrounds()

    def _background_option_line(row) -> str:
        name = str(getattr(row, "name", "Background") or "Background")
        profs = [str(item) for item in list(getattr(row, "proficiencies", []) or []) if str(item).strip()]
        prof_count = len(profs)
        gold = int(getattr(row, "starting_money", 0) or 0)
        return f"{name:<14} | Profs {prof_count:<2} | Gold {gold}"

    def _context_for(index: int) -> tuple[str, list[str]]:
        if index >= len(backgrounds):
            return "Creation Library", ["Open the reference library to browse backgrounds and roleplay guidance."]
        row = backgrounds[index]
        profs = [str(item) for item in list(getattr(row, "proficiencies", []) or []) if str(item).strip()]
        return (
            str(getattr(row, "name", "Background") or "Background"),
            [
                f"Feature: {str(getattr(row, 'feature', '') or '—')}",
                f"Proficiencies: {', '.join(profs) if profs else '—'}",
                f"Starting Gold: {int(getattr(row, 'starting_money', 0) or 0)}",
            ],
        )

    while True:
        options = [_background_option_line(row) for row in backgrounds] + ["Help: Creation Reference Library"]
        idx = _creation_menu(
            "Choose Your Origin",
            options,
            draft,
            footer_hint=_CREATION_HELP_HINT,
            context_provider=_context_for,
        )
        if idx < 0:
            return None
        if idx == len(options) - 1:
            _show_creation_reference_library(creation_service)
            continue
        return backgrounds[idx]


def _choose_subrace(creation_service, race, draft: CreationDraft):
    subraces = creation_service.list_subraces_for_race(race=race)
    if not subraces:
        return True, None

    def _subrace_option_line(row) -> str:
        name = str(getattr(row, "name", "Subrace") or "Subrace")
        speed_bonus = int(getattr(row, "speed_bonus", 0) or 0)
        bonuses = creation_service._format_bonus_line(getattr(row, "bonuses", {}) or {})
        return f"{name:<14} | {bonuses:<16} | Speed +{speed_bonus}"

    def _context_for(index: int) -> tuple[str, list[str]]:
        if index == 0:
            return "No Subrace", ["Skip subrace and continue with base race traits."]
        if index >= len(subraces) + 1:
            return "Creation Library", ["Open the reference library to browse subrace lore."]
        row = subraces[index - 1]
        traits = [str(item) for item in list(getattr(row, "traits", []) or []) if str(item).strip()]
        return (
            str(getattr(row, "name", "Subrace") or "Subrace"),
            [
                f"Speed Bonus: +{int(getattr(row, 'speed_bonus', 0) or 0)}",
                f"Bonuses: {creation_service._format_bonus_line(getattr(row, 'bonuses', {}) or {})}",
                f"Traits: {', '.join(traits) if traits else '—'}",
            ],
        )

    while True:
        options = ["No subrace"] + [_subrace_option_line(row) for row in subraces] + ["Help: Creation Reference Library"]
        idx = _creation_menu(
            "Choose a Subrace",
            options,
            draft,
            footer_hint=_CREATION_HELP_HINT,
            context_provider=_context_for,
        )
        if idx < 0:
            return False, None
        if idx == len(options) - 1:
            _show_creation_reference_library(creation_service)
            continue
        if idx == 0:
            return True, None
        return True, subraces[idx - 1]


def _choose_subclass(creation_service, chosen_class, draft: CreationDraft):
    subclass_rows = creation_service.list_subclasses_for_class(
        getattr(chosen_class, "slug", None) or getattr(chosen_class, "name", None)
    )
    if not subclass_rows:
        return True, None

    options = [str(getattr(row, "name", "Subclass") or "Subclass") for row in subclass_rows]
    options.append("Back")

    def _context_for(index: int) -> tuple[str, list[str]]:
        if index >= len(subclass_rows):
            return "Back", ["Return to class selection."]
        row = subclass_rows[index]
        return (
            str(getattr(row, "name", "Subclass") or "Subclass"),
            [str(getattr(row, "description", "") or "No description available.")],
        )

    idx = _creation_menu(
        "Choose Your Subclass",
        options,
        draft,
        footer_hint="ESC to return to class selection",
        context_provider=_context_for,
    )
    if idx < 0 or idx == len(options) - 1:
        return False, None
    return True, str(subclass_rows[idx].slug)


def _choose_difficulty(creation_service, draft: CreationDraft):
    difficulties = creation_service.list_difficulties()

    def _context_for(index: int) -> tuple[str, list[str]]:
        if index >= len(difficulties):
            return "Creation Library", ["Open the reference library for difficulty guidance."]
        row = difficulties[index]
        risk_label = str(getattr(row, "risk_label", "") or "")
        casualty_pressure = str(getattr(row, "casualty_pressure", "") or "")
        guardrail_warning = str(getattr(row, "guardrail_warning", "") or "")
        legacy_labels = [str(value) for value in list(getattr(row, "legacy_labels", []) or []) if str(value).strip()]
        lines = [
            str(getattr(row, "description", "") or ""),
            f"Risk: {risk_label or 'Unspecified'} | Casualty Pressure: {casualty_pressure or 'Unspecified'}",
            f"HP Multiplier: {float(getattr(row, 'hp_multiplier', 1.0) or 1.0):.2f}",
            f"Incoming Damage: x{float(getattr(row, 'incoming_damage_multiplier', 1.0) or 1.0):.2f}",
        ]
        if legacy_labels:
            lines.append(f"Legacy labels kept visible: {', '.join(legacy_labels)}")
        if guardrail_warning:
            lines.append(guardrail_warning)
        return (
            str(getattr(row, "name", "Difficulty") or "Difficulty"),
            lines,
        )

    while True:
        options = [str(getattr(row, "name", "Difficulty") or "Difficulty") for row in difficulties]
        options.append("Help: Creation Reference Library")
        idx = _creation_menu(
            "Difficulty",
            options,
            draft,
            footer_hint=_CREATION_HELP_HINT,
            context_provider=_context_for,
        )
        if idx < 0:
            return None
        if idx == len(options) - 1:
            _show_creation_reference_library(creation_service)
            continue
        return difficulties[idx]


def _choose_alignment(creation_service, draft: CreationDraft):
    alignments = creation_service.list_alignments()

    def _context_for(index: int) -> tuple[str, list[str]]:
        if index >= len(alignments):
            return "Creation Library", ["Open the reference library for alignment guidance."]
        value = str(alignments[index] or "").replace("_", " ").title()
        return (value, ["Roleplay compass for your character's decisions and tone."])

    while True:
        options = creation_service.alignment_option_labels() + ["Help: Creation Reference Library"]
        idx = _creation_menu(
            "Alignment",
            options,
            draft,
            footer_hint=_CREATION_HELP_HINT,
            context_provider=_context_for,
        )
        if idx < 0:
            return None
        if idx == len(options) - 1:
            _show_creation_reference_library(creation_service)
            continue
        return alignments[idx]


def _show_creation_reference_library(creation_service) -> bool:
    category_entries = list(getattr(creation_service, "CREATION_REFERENCE_CATEGORIES", ()))
    if not category_entries:
        return True

    while True:
        options = [label for _, label in category_entries] + ["Continue", "Back"]
        choice = arrow_menu("Creation Help Library", options, footer_hint="Study any topic, then choose Continue.")
        if choice in {-1, len(options) - 1}:
            return False
        if choice == len(options) - 2:
            return True

        slug, label = category_entries[choice]
        rows = creation_service.list_creation_reference_items(slug, limit=20)
        clear_screen()
        if _CONSOLE is not None and Panel is not None:
            if not rows:
                body = "No entries currently available."
            else:
                entries = [f"• {row}" for row in rows]
                if len(rows) >= 20:
                    entries.extend(["...", "(showing first 20 entries)"])
                body = "\n".join(entries)
            _CONSOLE.print(
                Panel.fit(
                    body,
                    title=f"[bold yellow]{label} Reference[/bold yellow]",
                    border_style=_PANEL_BORDER,
                )
            )
            _prompt_enter("Press ENTER to return...")
        else:
            print(f"=== {label} Reference ===")
            if not rows:
                print("No entries currently available.")
            else:
                for row in rows:
                    print(f"- {row}")
                if len(rows) >= 20:
                    print("...")
                    print("(showing first 20 entries)")
            _prompt_enter("Press ENTER to return...")


def _point_buy_prompt(
    creation_service,
    recommended: Dict[str, int],
    draft: CreationDraft,
) -> Dict[str, int] | None:
    ability_labels = {
        "STR": "Strength",
        "DEX": "Dexterity",
        "CON": "Constitution",
        "INT": "Intelligence",
        "WIS": "Wisdom",
        "CHA": "Charisma",
    }

    def _dashboard(
        title: str,
        left_title: str,
        left_lines: list[str],
        right_title: str,
        right_lines: list[str],
        footer: str,
    ):
        if Panel is None or Columns is None:
            return "\n".join([title, "", *left_lines, "", *right_lines, "", footer])

        left_panel = Panel.fit("\n".join(left_lines), title=f"[bold cyan]{left_title}[/bold cyan]", border_style="cyan")
        right_panel = Panel.fit("\n".join(right_lines), title=f"[bold cyan]{right_title}[/bold cyan]", border_style="cyan")

        if Layout is not None:
            layout = Layout(name="ability_dashboard")
            layout.split_column(
                Layout(Panel.fit(f"[bold yellow]{title}[/bold yellow]", border_style="cyan"), size=3),
                Layout(Columns([left_panel, right_panel], expand=True, equal=True), ratio=1),
                Layout(Panel.fit(footer, border_style="cyan"), size=3),
            )
            return layout

        return Columns([left_panel, right_panel], expand=True, equal=True)

    scores: Dict[str, int] = {ability: 8 for ability in ABILITY_ORDER}
    for ability in ABILITY_ORDER:
        value = int(recommended.get(ability, 8) or 8)
        scores[ability] = max(8, min(15, value))
    try:
        scores = creation_service.validate_point_buy(scores, pool=27)
    except ValueError:
        scores = {ability: 8 for ability in ABILITY_ORDER}

    selected = 0

    def _shift_score(index: int, delta: int) -> None:
        nonlocal scores
        ability = ABILITY_ORDER[index]
        proposed = int(scores.get(ability, 8) or 8) + int(delta)
        if proposed < 8 or proposed > 15:
            return
        candidate = dict(scores)
        candidate[ability] = proposed
        try:
            scores = creation_service.validate_point_buy(candidate, pool=27)
        except ValueError:
            return

    def _ability_mod(score: int) -> int:
        return (int(score) - 10) // 2

    def _render_point_buy_view():
        spent = int(creation_service.point_buy_cost(scores) or 0)
        remaining = max(0, 27 - spent)

        left_lines: list[str] = []
        for idx, ability in enumerate(ABILITY_ORDER):
            value = int(scores.get(ability, 8) or 8)
            mod = _ability_mod(value)
            mod_text = f"+{mod}" if mod >= 0 else str(mod)
            marker = "▶" if idx == selected else " "
            style = "bold black on bright_cyan" if idx == selected else "white"
            label = ability_labels.get(ability, ability)
            left_lines.append(f"[{style}]{marker} {label:<12}: {value:>2} ({mod_text:>3})[/{style}]")

        right_lines = [
            f"Remaining: [bold cyan]{remaining:02d}[/bold cyan] / 27",
            "",
            "Cost to increase:",
            "8 to 13 costs 1 point each.",
            "14 and 15 cost 2 points each.",
        ]

        return _dashboard(
            "ABILITY SCORE GENERATION (Point Buy)",
            "YOUR ATTRIBUTES",
            left_lines,
            "POINT POOL",
            right_lines,
            "[UP/DOWN] Select Attribute   [LEFT/RIGHT] Adjust Score   [ENTER] Confirm   [R] Reset   [ESC] Back",
        )

    if _CONSOLE is not None and Panel is not None and Columns is not None and Live is not None:
        clear_screen()
        with Live(_render_point_buy_view(), console=_CONSOLE, refresh_per_second=24, transient=True) as live:
            while True:
                draft.ability_scores = dict(scores)
                raw_key = read_key()
                key = normalize_menu_key(raw_key)
                lower_raw = str(raw_key or "").strip().lower()

                changed = False
                if key == "UP":
                    selected = (selected - 1) % len(ABILITY_ORDER)
                    changed = True
                elif key == "DOWN":
                    selected = (selected + 1) % len(ABILITY_ORDER)
                    changed = True
                elif key == "LEFT":
                    before = dict(scores)
                    _shift_score(selected, -1)
                    changed = before != scores
                elif key == "RIGHT":
                    before = dict(scores)
                    _shift_score(selected, 1)
                    changed = before != scores
                elif key == "ENTER":
                    return creation_service.validate_point_buy(dict(scores), pool=27)
                elif key == "ESC":
                    return None
                elif lower_raw == "r":
                    scores = dict(recommended)
                    changed = True
                elif lower_raw in {"h", "help", "?"}:
                    _show_creation_reference_library(creation_service)
                    changed = True

                if changed:
                    live.update(_render_point_buy_view(), refresh=True)
        return None

    while True:
        draft.ability_scores = dict(scores)
        clear_screen()
        spent = int(creation_service.point_buy_cost(scores) or 0)
        print("=== ABILITY SCORE GENERATION (Point Buy) ===")
        print(f"Remaining: {max(0, 27 - spent)} / 27")
        for idx, ability in enumerate(ABILITY_ORDER):
            marker = ">" if idx == selected else " "
            value = int(scores.get(ability, 8) or 8)
            mod = _ability_mod(value)
            mod_text = f"+{mod}" if mod >= 0 else str(mod)
            print(f"{marker} {ability}: {value} ({mod_text})")
        print("Use arrows (or W/S and A/D). ENTER confirm, R reset, ESC/Q back.")

        raw_key = read_key()
        key = normalize_menu_key(raw_key)
        lower_raw = str(raw_key or "").strip().lower()
        if key == "UP":
            selected = (selected - 1) % len(ABILITY_ORDER)
            continue
        if key == "DOWN":
            selected = (selected + 1) % len(ABILITY_ORDER)
            continue
        if key == "LEFT":
            _shift_score(selected, -1)
            continue
        if key == "RIGHT":
            _shift_score(selected, 1)
            continue
        if key == "ENTER":
            return creation_service.validate_point_buy(dict(scores), pool=27)
        if key == "ESC":
            return None
        if lower_raw == "r":
            scores = dict(recommended)
            continue
        if lower_raw in {"h", "help", "?"}:
            _show_creation_reference_library(creation_service)
            continue


def _roll_prompt(creation_service) -> Dict[str, int] | None:
    _ = creation_service
    return None


def _roll_assign_prompt(creation_service, chosen_class, draft: CreationDraft) -> Dict[str, int] | None:
    _ = creation_service
    ability_labels = {
        "STR": "Strength",
        "DEX": "Dexterity",
        "CON": "Constitution",
        "INT": "Intelligence",
        "WIS": "Wisdom",
        "CHA": "Charisma",
    }

    def _dashboard(
        title: str,
        left_title: str,
        left_lines: list[str],
        right_title: str,
        right_lines: list[str],
        center_title: str,
        center_lines: list[str],
        footer: str,
    ):
        if Panel is None or Columns is None:
            return "\n".join([title, "", *left_lines, "", *right_lines, "", *center_lines, "", footer])

        left_panel = Panel.fit("\n".join(left_lines), title=f"[bold cyan]{left_title}[/bold cyan]", border_style="cyan")
        right_panel = Panel.fit("\n".join(right_lines), title=f"[bold cyan]{right_title}[/bold cyan]", border_style="cyan")
        center_panel = Panel.fit("\n".join(center_lines), title=f"[bold cyan]{center_title}[/bold cyan]", border_style="cyan")

        if Layout is not None:
            layout = Layout(name="ability_dashboard")
            layout.split_column(
                Layout(Panel.fit(f"[bold yellow]{title}[/bold yellow]", border_style="cyan"), size=3),
                Layout(Columns([left_panel, right_panel], expand=True, equal=True), size=11),
                Layout(center_panel, ratio=1),
                Layout(Panel.fit(footer, border_style="cyan"), size=3),
            )
            return layout

        return Columns([left_panel, right_panel], expand=True, equal=True)

    rolled_rows: list[tuple[int, list[int]]] = []

    selected = 0
    assigned: dict[str, int] = {}
    rolling_feed: list[str] = ["Rolling 4d6 (drop lowest) for 6 values..."]
    rolling_trail: list[str] = []
    is_rolling = True
    rolling_preview = [1, 1, 1, 1]
    roll_rng = random.Random()
    frame_counter = 0
    waiting_for_roll_continue = False
    waiting_roll_number = 0

    def _ability_mod(score: int) -> int:
        return (int(score) - 10) // 2

    def _assigned_slot(slot_index: int) -> str:
        for ability, value in assigned.items():
            if int(value) == int(slot_index):
                return ability
        return ""

    def _compute_best_assignment() -> dict[str, int]:
        template = dict(creation_service.standard_array_for_class(chosen_class) or {})

        def _score_for(ability: str) -> int:
            value = template.get(ability)
            if value is None:
                value = template.get(str(ability).lower())
            return int(value or 8)

        ranked_abilities = sorted(list(ABILITY_ORDER), key=_score_for, reverse=True)
        ranked_slots = sorted(range(len(rolled_rows)), key=lambda idx: int(rolled_rows[idx][0]), reverse=True)

        best: dict[str, int] = {}
        for idx, ability in enumerate(ranked_abilities):
            if idx >= len(ranked_slots):
                break
            best[str(ability)] = int(ranked_slots[idx])
        return best

    def _render_assign_view():
        left_lines: list[str] = []
        for idx, ability in enumerate(ABILITY_ORDER):
            marker = "▶" if idx == selected else " "
            slot_index = assigned.get(ability)
            label = ability_labels.get(ability, ability)
            if slot_index is None:
                line = f"{marker} {label:<12}: [grey70]--[/grey70]"
            else:
                value, _dice = rolled_rows[int(slot_index)]
                mod = _ability_mod(int(value))
                mod_text = f"+{mod}" if mod >= 0 else str(mod)
                line = f"{marker} {label:<12}: [bold green]{int(value):>2}[/bold green] ({mod_text:>3})"
            style = "bold black on bright_cyan" if idx == selected else "white"
            left_lines.append(f"[{style}]{line}[/{style}]")

        right_lines: list[str] = []
        for idx, row in enumerate(rolled_rows, start=1):
            value, dice = row
            owner = _assigned_slot(idx - 1)
            dice_text = ", ".join(str(int(token)) for token in list(dice or []))
            if owner:
                right_lines.append(f"[{idx}] [grey70]{int(value):>2} ({dice_text}) [Assigned to {owner}][/grey70]")
            else:
                right_lines.append(f"[{idx}] {int(value):>2} ({dice_text})")

        if is_rolling:
            complete = len(rolled_rows)
            progress_bar = f"[{'█' * complete}{'░' * (6 - complete)}] {complete}/6"
            trail_rows = list(rolling_trail[-14:])
            if len(trail_rows) < 14:
                trail_rows.extend(["[dim]·[/dim]"] * (14 - len(trail_rows)))
            continue_line = "[bold cyan]ENTER next roll • SPACE fast-forward • ESC cancel[/bold cyan]" if waiting_for_roll_continue else ""
            center_lines = [
                f"Rolling set {len(rolled_rows) + 1} / 6",
                f"Progress: {progress_bar}",
                f"Preview dice: ({', '.join(str(int(row)) for row in list(rolling_preview))})",
                "",
                continue_line,
                *trail_rows,
            ]
        else:
            center_lines = [
                "Rolling complete.",
                f"Progress: [{'█' * 6}] 6/6",
                "",
                *rolling_feed[-10:],
            ]
            if not center_lines:
                center_lines = ["Ready to assign scores."]

        return _dashboard(
            "ABILITY SCORE GENERATION (Roll 4d6, Drop Lowest)",
            "ASSIGN SCORES",
            left_lines,
            "ROLLED VALUES",
            right_lines,
            "ROLL FEED",
            center_lines,
            "[UP/DOWN] Select Attribute   [1-6] Assign Roll   [B] Best Auto-Assign   [R] Reset   [ENTER] Confirm   [ESC] Back",
        )

    if _CONSOLE is not None and Panel is not None and Columns is not None and Live is not None:
        clear_screen()
        fast_forward_remaining = False
        with Live(_render_assign_view(), console=_CONSOLE, refresh_per_second=24, transient=True) as live:
            for roll_index in range(6):
                for frame_idx in range(8):
                    rolling_preview = [roll_rng.randint(1, 6) for _ in range(4)]
                    spinner = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
                    rolling_trail.append(
                        f"{spinner[frame_counter % len(spinner)]} S{roll_index + 1} F{frame_idx + 1}: "
                        f"({', '.join(str(int(token)) for token in rolling_preview)})"
                    )
                    if len(rolling_trail) > 240:
                        rolling_trail = rolling_trail[-240:]
                    frame_counter += 1
                    live.update(_render_assign_view(), refresh=True)
                    time.sleep(0.04)

                final_dice = [roll_rng.randint(1, 6) for _ in range(4)]
                total = int(sum(final_dice) - min(final_dice))
                rolled_rows.append((total, list(final_dice)))
                rolling_feed.append(
                    f"[{roll_index + 1}] {total:>2} ({', '.join(str(int(token)) for token in final_dice)})"
                )
                rolling_trail.append(
                    f"[bold green]✓[/bold green] S{roll_index + 1} locked: "
                    f"{total:>2} ({', '.join(str(int(token)) for token in final_dice)})"
                )
                rolling_preview = list(final_dice)
                waiting_for_roll_continue = True
                waiting_roll_number = int(roll_index + 1)
                live.update(_render_assign_view(), refresh=True)

                if not fast_forward_remaining:
                    while True:
                        raw_wait_key = read_key()
                        key = normalize_menu_key(raw_wait_key)
                        raw_wait = str(raw_wait_key or "")
                        if key == "ENTER":
                            waiting_for_roll_continue = False
                            waiting_roll_number = 0
                            break
                        if raw_wait == " ":
                            fast_forward_remaining = True
                            waiting_for_roll_continue = False
                            waiting_roll_number = 0
                            rolling_trail.append("[bold cyan]⏩ Fast-forward enabled for remaining rolls[/bold cyan]")
                            break
                        if key == "ESC":
                            return None
                else:
                    waiting_for_roll_continue = False
                    waiting_roll_number = 0

                rolling_trail.append(f"[dim]Continuing after roll {waiting_roll_number or (roll_index + 1)}...[/dim]")
                live.update(_render_assign_view(), refresh=True)

            is_rolling = False
            live.update(_render_assign_view(), refresh=True)

            while True:
                draft_scores: Dict[str, int] = {}
                for ability in ABILITY_ORDER:
                    slot = assigned.get(ability)
                    if slot is None:
                        continue
                    draft_scores[str(ability)] = int(rolled_rows[int(slot)][0])
                draft.ability_scores = dict(draft_scores)

                raw_key = read_key()
                key = normalize_menu_key(raw_key)
                raw = str(raw_key or "").strip().lower()
                changed = False

                if key == "UP":
                    selected = (selected - 1) % len(ABILITY_ORDER)
                    changed = True
                elif key == "DOWN":
                    selected = (selected + 1) % len(ABILITY_ORDER)
                    changed = True
                elif key == "ESC":
                    return None
                elif key == "ENTER":
                    if len(assigned) == len(ABILITY_ORDER):
                        return {ability: int(rolled_rows[int(slot)][0]) for ability, slot in assigned.items()}
                elif raw == "r":
                    assigned = {}
                    changed = True
                elif raw == "b":
                    assigned = _compute_best_assignment()
                    changed = True
                elif raw in {"h", "help", "?"}:
                    _show_creation_reference_library(creation_service)
                    changed = True
                elif raw in {"1", "2", "3", "4", "5", "6"}:
                    slot_index = int(raw) - 1
                    if 0 <= slot_index < len(rolled_rows):
                        owner = _assigned_slot(slot_index)
                        if owner and owner != ABILITY_ORDER[selected]:
                            changed = False
                        else:
                            assigned[ABILITY_ORDER[selected]] = slot_index
                            changed = True

                if changed:
                    live.update(_render_assign_view(), refresh=True)
        return None

    clear_screen()
    print("Roll assignment requires Rich interactive mode. Falling back to direct rolled assignment.")
    rolled = roll_attributes_with_animation()
    return {abbr: int(rolled.get(abbr, 8) or 8) for abbr in ATTR_ORDER}


def _choose_abilities(creation_service, chosen_class, draft: CreationDraft):
    while True:
        methods = [
            "Class template (standard array)",
            "Point buy (27 points)",
            "Roll 4d6 drop lowest",
            "Help: Creation Reference Library",
        ]
        method = _creation_menu("Ability Scores", methods, draft, footer_hint=_CREATION_HELP_HINT)
        if method < 0:
            return None
        if method == 3:
            _show_creation_reference_library(creation_service)
            continue

        if method == 1:
            recommended = creation_service.standard_array_for_class(chosen_class)
            return _point_buy_prompt(creation_service, recommended, draft)
        if method == 2:
            return _roll_assign_prompt(creation_service, chosen_class, draft)

        return creation_service.standard_array_for_class(chosen_class)


def _choose_equipment(creation_service, chosen_class, draft: CreationDraft) -> dict[str, object] | None:
    class_slug = str(getattr(chosen_class, "slug", "") or "").strip().lower()
    options = list(creation_service.get_starting_equipment_options(class_slug) or [])
    if not options:
        return {"mode": "standard_equipment", "items": [], "gold_bonus": 0, "label": "No equipment options"}

    while True:
        labels = [str(row.get("label", "Option") or "Option") for row in options]
        labels.append("Help: Creation Reference Library")

        def _context_for(index: int) -> tuple[str, list[str]]:
            if index >= len(options):
                return "Creation Library", ["Open the reference library for equipment tables and gear details."]
            row = options[index]
            items = [str(item) for item in list(row.get("items", []) or []) if str(item).strip()]
            if str(row.get("id", "")) == "starting_gold":
                spec = str(row.get("gold_spec", "") or "4d4x10")
                return ("Starting Gold", [f"Roll gold by: {spec}", "Start with coin and buy gear in town."])
            return (
                "Equipment Package",
                [f"Items: {', '.join(items) if items else '—'}"],
            )

        idx = _creation_menu(
            "Starting Equipment",
            labels,
            draft,
            footer_hint=_CREATION_HELP_HINT,
            context_provider=_context_for,
        )
        if idx < 0:
            return None
        if idx == len(labels) - 1:
            _show_creation_reference_library(creation_service)
            continue
        selected = options[idx]
        return creation_service.resolve_starting_equipment_choice(class_slug, str(selected.get("id", "") or ""))


def _select_spells_from_pool(
    creation_service,
    draft: CreationDraft,
    *,
    title: str,
    pool: list[str],
    target_count: int,
    footer_hint: str,
) -> list[str] | None:
    if target_count <= 0:
        return []
    selected: list[str] = []

    while True:
        labels: list[str] = []
        for spell_name in pool:
            marker = "[x]" if spell_name in selected else "[ ]"
            labels.append(f"{marker} {spell_name}")
        labels.extend([
            f"Confirm Selection ({len(selected)}/{target_count})",
            "Help: Creation Reference Library",
        ])
        pick = _creation_menu(title, labels, draft, footer_hint=footer_hint)
        if pick < 0:
            return None
        if pick == len(labels) - 1:
            _show_creation_reference_library(creation_service)
            continue
        if pick == len(labels) - 2:
            if len(selected) >= target_count:
                return selected[:target_count]
            continue

        chosen_spell = pool[pick]
        if chosen_spell in selected:
            selected = [row for row in selected if row != chosen_spell]
        elif len(selected) < target_count:
            selected.append(chosen_spell)


def _select_multi_from_pool(
    title: str,
    pool: list[str],
    target_count: int,
    draft: CreationDraft,
    *,
    footer_hint: str,
) -> list[str] | None:
    if target_count <= 0:
        return []
    selected: list[str] = []
    while True:
        options = []
        for row in pool:
            marker = "[x]" if row in selected else "[ ]"
            options.append(f"{marker} {row}")
        options.extend([
            f"Confirm Selection ({len(selected)}/{target_count})",
            "Back",
        ])
        choice = _creation_menu(title, options, draft, footer_hint=footer_hint)
        if choice in {-1, len(options) - 1}:
            return None
        if choice == len(options) - 2:
            if len(selected) >= target_count:
                return selected[:target_count]
            continue
        picked = pool[choice]
        if picked in selected:
            selected = [row for row in selected if row != picked]
        elif len(selected) < target_count:
            selected.append(picked)


def _prompt_profile_value(title: str, prompt: str, draft: CreationDraft, default_value: str = "") -> str | None:
    clear_screen()
    if _CONSOLE is not None and Panel is not None and Columns is not None:
        left = Panel.fit(
            "\n".join([
                prompt,
                "Type [bold]esc[/bold] to go back.",
            ]),
            title=f"[bold yellow]{title}[/bold yellow]",
            border_style=_PANEL_BORDER,
        )
        _CONSOLE.print(Columns([left, _draft_panel(draft)], expand=True, equal=True))
        raw = _CONSOLE.input("[bold yellow]>>> [/bold yellow]").strip()
    else:
        print(f"=== {title} ===")
        print(prompt)
        print("Type 'esc' to go back.")
        raw = input(">>> ").strip()
    if str(raw).strip().lower() in {"esc", "q", "quit", "back"}:
        return None
    if not raw:
        return str(default_value or "").strip()
    return raw


def _choose_background_extras(creation_service, background, draft: CreationDraft) -> dict[str, list[str]] | None:
    profile = creation_service.list_background_choice_options(getattr(background, "name", ""))
    tool_choices = int(profile.get("tool_choices", 0) or 0)
    language_choices = int(profile.get("language_choices", 0) or 0)
    tool_pool = [str(row) for row in list(profile.get("tool_pool", []) or []) if str(row).strip()]
    language_pool = [str(row) for row in list(profile.get("language_pool", []) or []) if str(row).strip()]

    selected_tools: list[str] = []
    selected_languages: list[str] = []

    if tool_choices > 0 and tool_pool:
        picks = _select_multi_from_pool(
            "Choose Tool Proficiencies",
            tool_pool,
            tool_choices,
            draft,
            footer_hint=f"Select {tool_choices} tool proficiency choice(s).",
        )
        if picks is None:
            return None
        selected_tools = list(picks)

    if language_choices > 0 and language_pool:
        picks = _select_multi_from_pool(
            "Choose Languages",
            language_pool,
            language_choices,
            draft,
            footer_hint=f"Select {language_choices} language choice(s).",
        )
        if picks is None:
            return None
        selected_languages = list(picks)

    return {
        "tools": selected_tools,
        "languages": selected_languages,
    }


def _choose_personality_profile(creation_service, background, draft: CreationDraft) -> dict[str, str] | None:
    while True:
        choice = _creation_menu(
            "Personality Profile",
            [
                "Roll from background table",
                "Enter manually",
                "Keep default placeholders",
                "Help: Creation Reference Library",
            ],
            draft,
            footer_hint="Trait, Ideal, Bond, Flaw can be rolled or written.",
        )
        if choice < 0:
            return None
        if choice == 3:
            _show_creation_reference_library(creation_service)
            continue
        if choice == 2:
            return {
                "trait": "",
                "ideal": "",
                "bond": "",
                "flaw": "",
            }
        if choice == 0:
            return creation_service.roll_background_personality(getattr(background, "name", ""))

        trait = _prompt_profile_value("Personality Trait", "Describe your character's defining trait.", draft)
        if trait is None:
            continue
        ideal = _prompt_profile_value("Ideal", "What principle drives your character?", draft)
        if ideal is None:
            continue
        bond = _prompt_profile_value("Bond", "Who or what is your character bound to?", draft)
        if bond is None:
            continue
        flaw = _prompt_profile_value("Flaw", "What weakness complicates your character?", draft)
        if flaw is None:
            continue
        return {
            "trait": str(trait or ""),
            "ideal": str(ideal or ""),
            "bond": str(bond or ""),
            "flaw": str(flaw or ""),
        }


def _choose_level1_class_features(creation_service, chosen_class, draft: CreationDraft) -> dict[str, object] | None:
    class_slug = str(getattr(chosen_class, "slug", "") or "").strip().lower()
    profile = dict(creation_service.list_level1_class_feature_choices(class_slug) or {})
    if not profile:
        return {}

    if "fighting_style" in profile:
        options = [str(row) for row in list(profile.get("fighting_style", []) or []) if str(row).strip()]
        labels = list(options) + ["Back"]
        choice = _creation_menu("Choose Fighting Style", labels, draft, footer_hint="Level 1 Fighter feature")
        if choice in {-1, len(labels) - 1}:
            return None
        return {"fighting_style": options[choice]}

    if "expertise_pool" in profile:
        pool = [str(row) for row in list(profile.get("expertise_pool", []) or []) if str(row).strip()]
        target = max(1, int(profile.get("expertise_count", 2) or 2))
        picks = _select_multi_from_pool(
            "Choose Rogue Expertise",
            pool,
            target,
            draft,
            footer_hint=f"Select {target} skills for Expertise.",
        )
        if picks is None:
            return None
        return {"expertise_skills": list(picks)}

    if "draconic_ancestry" in profile:
        options = [str(row) for row in list(profile.get("draconic_ancestry", []) or []) if str(row).strip()]
        labels = list(options) + ["Back"]
        choice = _creation_menu("Choose Draconic Ancestry", labels, draft, footer_hint="Level 1 Sorcerer feature")
        if choice in {-1, len(labels) - 1}:
            return None
        return {"draconic_ancestry": options[choice]}

    return {}


def _choose_level1_feat(creation_service, race, selected_subrace, draft: CreationDraft) -> str | None:
    race_name = str(getattr(race, "name", "") or "")
    subrace_name = str(getattr(selected_subrace, "name", "") or "")
    if not creation_service.is_feat_selection_eligible(race_name, subrace_name):
        return ""

    options = list(creation_service.list_level1_feat_options() or [])
    labels = [str(row.get("label", row.get("slug", "Feat")) or "Feat") for row in options]
    labels.extend(["Skip feat", "Back"])

    def _context_for(index: int) -> tuple[str, list[str]]:
        if index >= len(options):
            return "Feat Selection", ["Pick a feat now or skip this optional edge-case choice."]
        row = options[index]
        label = str(row.get("label", "Feat") or "Feat")
        return (label, ["Level 1 bonus feature. Grants early specialization."])

    choice = _creation_menu(
        "Choose Level 1 Feat",
        labels,
        draft,
        footer_hint="Variant Human / Custom Lineage",
        context_provider=_context_for,
    )
    if choice in {-1, len(labels) - 1}:
        return None
    if choice == len(labels) - 2:
        return ""
    return str(options[choice].get("slug", "") or "")


def _choose_spells(creation_service, chosen_class, race, selected_subrace, draft: CreationDraft) -> dict[str, list[str]] | None:
    class_slug = str(getattr(chosen_class, "slug", "") or "").strip().lower()
    race_name = str(getattr(race, "name", "") or "")
    subrace_name = str(getattr(selected_subrace, "name", "") or "")
    profile = creation_service.list_starting_spell_options(
        class_slug,
        race_name=race_name,
        subrace_name=subrace_name,
    )
    if not bool(profile.get("spellcasting", False)):
        return {"cantrips": [], "spells": []}

    granted_cantrips = [str(row) for row in list(profile.get("granted_cantrips", []) or []) if str(row).strip()]
    granted_spells = [str(row) for row in list(profile.get("granted_spells", []) or []) if str(row).strip()]
    required_cantrips = max(0, int(profile.get("required_cantrips", 0) or 0) - len(granted_cantrips))
    required_spells = max(0, int(profile.get("required_spells", 0) or 0) - len(granted_spells))

    cantrip_pool = [str(row) for row in list(profile.get("cantrip_pool", []) or []) if str(row).strip()]
    spell_pool = [str(row) for row in list(profile.get("spell_pool", []) or []) if str(row).strip()]

    selected_cantrips: list[str] = []
    selected_spells: list[str] = []

    if required_cantrips > 0:
        picked = _select_spells_from_pool(
            creation_service,
            draft,
            title="Select Cantrips",
            pool=cantrip_pool,
            target_count=required_cantrips,
            footer_hint=f"Choose {required_cantrips} cantrip(s).",
        )
        if picked is None:
            return None
        selected_cantrips = list(picked)

    if required_spells > 0:
        picked = _select_spells_from_pool(
            creation_service,
            draft,
            title="Select 1st-Level Spells",
            pool=spell_pool,
            target_count=required_spells,
            footer_hint=f"Choose {required_spells} spell(s).",
        )
        if picked is None:
            return None
        selected_spells = list(picked)

    return {
        "cantrips": [*granted_cantrips, *selected_cantrips],
        "spells": [*granted_spells, *selected_spells],
    }


def _show_cancelled():
    clear_screen()
    if _CONSOLE is not None and Panel is not None:
        _CONSOLE.print(
            Panel.fit(
                "Character creation canceled.",
                title="[bold yellow]Character Creation[/bold yellow]",
                border_style=_PANEL_BORDER,
            )
        )
        _prompt_enter("Press ENTER to return to the menu...")
        return

    print("Character creation canceled.")
    _prompt_enter("Press ENTER to return to the menu...")


def _run_creation_skill_training_flow(game_service, character_id: int) -> None:
    initialize = game_service.initialize_skill_training_intent(
        character_id,
        grant_level_points=True,
    )
    clear_screen()
    if _CONSOLE is not None and Panel is not None:
        _CONSOLE.print(
            Panel.fit(
                "\n".join(list(initialize.messages or ["Skill training prepared."])),
                title="[bold yellow]Skill Training[/bold yellow]",
                border_style=_PANEL_BORDER,
            )
        )
    else:
        print("=== Skill Training ===")
        for line in list(initialize.messages or ["Skill training prepared."]):
            print(str(line))
    _prompt_enter()

    status = game_service.get_skill_training_status_intent(character_id)
    intent = [str(row) for row in list(status.get("intent", []))]

    while True:
        status = game_service.get_skill_training_status_intent(character_id)
        points = int(status.get("points_available", 0) or 0)
        if points <= 0:
            return

        skills = list(game_service.list_granular_skills_intent(character_id) or [])
        options: list[str] = []
        slugs: list[str] = []
        for row in skills:
            slug = str(row.get("slug", "") or "")
            if not slug:
                continue
            current = int(row.get("current", 0) or 0)
            eligible_new = bool(row.get("eligible_new", False))
            if current <= 0 and not eligible_new:
                continue
            label = str(row.get("label", slug)).strip() or slug
            marker = "[x]" if slug in intent else "[ ]"
            options.append(f"{marker} {label} (+{current})")
            slugs.append(slug)

        options.extend(["Help: Creation Reference Library", "Finish"])
        pick = arrow_menu(f"Skill Allocation ({points} left)", options, footer_hint="Select a skill to allocate 1 point.")
        if pick in {-1, len(options) - 1}:
            return
        if pick == len(options) - 2:
            _show_creation_reference_library(game_service.character_creation_service)
            continue

        selected_slug = slugs[pick]
        if selected_slug not in intent:
            intent.append(selected_slug)
            game_service.declare_skill_training_intent_intent(character_id, intent)

        result = game_service.spend_skill_proficiency_points_intent(character_id, {selected_slug: 1})
        clear_screen()
        if _CONSOLE is not None and Panel is not None:
            _CONSOLE.print(
                Panel.fit(
                    "\n".join(list(result.messages or ["No changes applied."])),
                    title="[bold yellow]Skill Training[/bold yellow]",
                    border_style=_PANEL_BORDER,
                )
            )
        else:
            print("=== Skill Training ===")
            for line in list(result.messages or ["No changes applied."]):
                print(str(line))
        _prompt_enter()


def run_character_creation(game_service):
    creation_service = game_service.character_creation_service
    if creation_service is None:
        raise RuntimeError("Character creation is unavailable.")

    classes = creation_service.list_classes()
    if not classes:
        clear_screen()
        print("No classes available.")
        _prompt_enter("Press ENTER to return to the menu...")
        return None

    draft = CreationDraft()
    state_keys = [
        "race",
        "subrace",
        "name_gender",
        "name",
        "class",
        "subclass",
        "equipment",
        "spells",
        "abilities",
        "background",
        "background_extras",
        "personality",
        "class_feature",
        "feat",
        "difficulty",
        "alignment",
    ]
    step_labels = [
        "Race",
        "Subrace",
        "Gender",
        "Name",
        "Class",
        "Subclass",
        "Equipment",
        "Spells",
        "Abilities",
        "Background",
        "Proficiencies",
        "Personality",
        "Class Feature",
        "Feat",
        "Difficulty",
        "Finish",
    ]
    current_step = 0

    race = None
    selected_subrace = None
    chosen_class = None
    chosen_class_index = -1
    selected_subclass_slug = None
    background = None
    difficulty = None
    alignment = None
    selected_equipment_override: list[str] | None = None
    selected_starting_gold_bonus = 0
    selected_cantrips: list[str] | None = None
    selected_known_spells: list[str] | None = None
    selected_tool_proficiencies: list[str] | None = None
    selected_languages: list[str] | None = None
    selected_personality_profile: dict[str, str] | None = None
    selected_class_feature_choices: dict[str, object] | None = None
    selected_feat_slug: str | None = None

    def _sync_draft_details() -> None:
        draft.auto_languages = _race_auto_languages(
            str(getattr(race, "name", "") or ""),
            str(getattr(selected_subrace, "name", "") or ""),
        )

        trait_rows: list[str] = []
        for source in [race, selected_subrace]:
            if source is None:
                continue
            for row in list(getattr(source, "traits", []) or []):
                text = str(row).strip()
                if text and text not in trait_rows:
                    trait_rows.append(text)
        draft.racial_traits = list(trait_rows)

        draft.chosen_languages = [str(row) for row in list(selected_languages or []) if str(row).strip()]
        draft.chosen_tools = [str(row) for row in list(selected_tool_proficiencies or []) if str(row).strip()]

    while 0 <= current_step < len(state_keys):
        key = state_keys[current_step]
        draft.progress_steps = list(step_labels)
        draft.progress_index = int(current_step)
        _sync_draft_details()

        if key == "name":
            confirmed_name, raw_name = _choose_name(creation_service, draft)
            if not confirmed_name:
                _show_cancelled()
                return None
            draft.name = str(raw_name or "")
            current_step += 1
            continue

        if key == "race":
            picked = _choose_race(creation_service, draft)
            if picked is None:
                if current_step == 0:
                    _show_cancelled()
                    return None
                current_step -= 1
                continue
            race = picked
            selected_subrace = None
            draft.race = str(getattr(race, "name", "") or "")
            draft.subrace = ""
            current_step += 1
            continue

        if key == "subrace":
            confirmed_subrace, selected_subrace = _choose_subrace(creation_service, race, draft)
            if not confirmed_subrace:
                current_step -= 1
                continue
            draft.subrace = str(getattr(selected_subrace, "name", "") or "")
            current_step += 1
            continue

        if key == "name_gender":
            selected_gender = _choose_name_generation_gender(draft)
            if selected_gender is None:
                current_step -= 1
                continue
            draft.name_gender = str(selected_gender)
            current_step += 1
            continue

        if key == "class":
            options = creation_service.list_class_names() + ["Help: Creation Reference Library"]

            def _context_for(index: int) -> tuple[str, list[str]]:
                if index >= len(classes):
                    return "Creation Library", ["Open the reference library to compare classes."]
                row = classes[index]
                return (
                    str(getattr(row, "name", "Class") or "Class"),
                    [
                        f"[{_THEME['attributes']}]Primary Ability[/{_THEME['attributes']}]: {str(getattr(row, 'primary_ability', '—') or '—').title()}",
                        f"[{_THEME['attributes']}]Hit Die[/{_THEME['attributes']}]: {str(getattr(row, 'hit_die', 'd8') or 'd8')}",
                        f"Recommended: {creation_service.format_attribute_line(getattr(row, 'base_attributes', {}) or {})}",
                    ],
                )

            idx = _creation_menu(
                "Choose Your Class",
                options,
                draft,
                footer_hint=_CREATION_HELP_HINT,
                context_provider=_context_for,
            )
            if idx < 0:
                current_step -= 1
                continue
            if idx == len(options) - 1:
                _show_creation_reference_library(creation_service)
                continue
            chosen = classes[idx]
            if not _show_class_detail(creation_service, chosen, draft):
                continue
            chosen_class = chosen
            chosen_class_index = idx
            selected_subclass_slug = None
            draft.class_name = str(getattr(chosen_class, "name", "") or "")
            draft.subclass_name = ""
            draft.equipment = ""
            draft.spells = ""
            selected_equipment_override = None
            selected_starting_gold_bonus = 0
            selected_cantrips = None
            selected_known_spells = None
            selected_tool_proficiencies = None
            selected_languages = None
            selected_personality_profile = None
            selected_class_feature_choices = None
            selected_feat_slug = None
            current_step += 1
            continue

        if key == "subclass":
            unlock_level = int(creation_service.subclass_selection_level_for_class(getattr(chosen_class, "slug", "") or "") or 3)
            if unlock_level > 1:
                selected_subclass_slug = None
                draft.subclass_name = f"Unlocks at level {unlock_level}"
                current_step += 1
                continue

            subclass_confirmed, selected_subclass_slug = _choose_subclass(creation_service, chosen_class, draft)
            if not subclass_confirmed:
                current_step -= 1
                continue
            if selected_subclass_slug:
                resolved_rows = creation_service.list_subclasses_for_class(
                    getattr(chosen_class, "slug", None) or getattr(chosen_class, "name", None)
                )
                selected = next((row for row in resolved_rows if str(getattr(row, "slug", "")) == str(selected_subclass_slug)), None)
                draft.subclass_name = str(getattr(selected, "name", "") or "")
            else:
                draft.subclass_name = ""
            current_step += 1
            continue

        if key == "equipment":
            equipment_payload = _choose_equipment(creation_service, chosen_class, draft)
            if equipment_payload is None:
                current_step -= 1
                continue
            selected_equipment_override = list(equipment_payload.get("items", []) or [])
            selected_starting_gold_bonus = int(equipment_payload.get("gold_bonus", 0) or 0)
            mode = str(equipment_payload.get("mode", "standard_equipment") or "standard_equipment")
            if mode == "starting_gold":
                draft.equipment = f"Starting Gold (+{selected_starting_gold_bonus}g)"
            else:
                draft.equipment = str(equipment_payload.get("label", "Standard equipment") or "Standard equipment")
            current_step += 1
            continue

        if key == "spells":
            spell_payload = _choose_spells(creation_service, chosen_class, race, selected_subrace, draft)
            if spell_payload is None:
                current_step -= 1
                continue
            selected_cantrips = [str(row) for row in list(spell_payload.get("cantrips", []) or []) if str(row).strip()]
            selected_known_spells = [str(row) for row in list(spell_payload.get("spells", []) or []) if str(row).strip()]
            if selected_cantrips or selected_known_spells:
                draft.spells = f"{len(selected_cantrips)} cantrip(s), {len(selected_known_spells)} spell(s)"
            else:
                draft.spells = "No level-1 spell picks"
            current_step += 1
            continue

        if key == "abilities":
            ability_scores = _choose_abilities(creation_service, chosen_class, draft)
            if ability_scores is None:
                current_step -= 1
                continue
            draft.ability_scores = dict(ability_scores)
            current_step += 1
            continue

        if key == "background":
            background = _choose_background(creation_service, draft)
            if background is None:
                current_step -= 1
                continue
            draft.background = str(getattr(background, "name", "") or "")
            selected_tool_proficiencies = None
            selected_languages = None
            selected_personality_profile = None
            current_step += 1
            continue

        if key == "background_extras":
            extras = _choose_background_extras(creation_service, background, draft)
            if extras is None:
                current_step -= 1
                continue
            selected_tool_proficiencies = [str(row) for row in list(extras.get("tools", []) or []) if str(row).strip()]
            selected_languages = [str(row) for row in list(extras.get("languages", []) or []) if str(row).strip()]
            current_step += 1
            continue

        if key == "personality":
            personality = _choose_personality_profile(creation_service, background, draft)
            if personality is None:
                current_step -= 1
                continue
            selected_personality_profile = dict(personality)
            current_step += 1
            continue

        if key == "class_feature":
            feature_payload = _choose_level1_class_features(creation_service, chosen_class, draft)
            if feature_payload is None:
                current_step -= 1
                continue
            selected_class_feature_choices = dict(feature_payload)
            current_step += 1
            continue

        if key == "feat":
            feat_slug = _choose_level1_feat(creation_service, race, selected_subrace, draft)
            if feat_slug is None:
                current_step -= 1
                continue
            selected_feat_slug = str(feat_slug or "")
            current_step += 1
            continue

        if key == "difficulty":
            difficulty = _choose_difficulty(creation_service, draft)
            if difficulty is None:
                current_step -= 1
                continue
            draft.difficulty = str(getattr(difficulty, "name", "") or "")
            current_step += 1
            continue

        if key == "alignment":
            alignment = _choose_alignment(creation_service, draft)
            if alignment is None:
                current_step -= 1
                continue
            draft.alignment = str(alignment).replace("_", " ").title()
            current_step += 1
            continue

    character = creation_service.create_character(
        name=draft.name,
        class_index=chosen_class_index,
        ability_scores=draft.ability_scores,
        race=race,
        subrace=selected_subrace,
        background=background,
        difficulty=difficulty,
        subclass_slug=selected_subclass_slug,
        alignment=alignment,
        starting_equipment_override=selected_equipment_override,
        starting_gold_bonus=int(selected_starting_gold_bonus),
        selected_cantrips=selected_cantrips,
        selected_known_spells=selected_known_spells,
        selected_tool_proficiencies=selected_tool_proficiencies,
        selected_languages=selected_languages,
        personality_profile=selected_personality_profile,
        class_feature_choices=selected_class_feature_choices,
        selected_feat_slug=selected_feat_slug,
        generated_name_gender=str(getattr(draft, "name_gender", "") or "").strip().lower() or None,
    )
    summary = game_service.build_character_creation_summary(character)

    clear_screen()
    _render_character_summary(summary)
    _run_creation_skill_training_flow(game_service, summary.character_id)
    print("")
    _prompt_enter("Press ENTER to begin your adventure...")
    return summary.character_id
