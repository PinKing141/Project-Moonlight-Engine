from typing import Dict

from rpg.application.services.character_creation_service import ABILITY_ORDER
from rpg.presentation.menu_controls import arrow_menu, clear_screen, read_key, normalize_menu_key
from rpg.presentation.rolling_ui import roll_attributes_with_animation, ATTR_ORDER

try:
    from rich.console import Console
    from rich.panel import Panel
except Exception:  # pragma: no cover - optional dependency fallback
    Console = None
    Panel = None


_CONSOLE = Console() if Console is not None else None
_CREATION_HELP_HINT = "Need guidance? Open the Creation Library."
_PANEL_BORDER = "yellow"


def _prompt_enter(message: str = "Press ENTER to continue...") -> None:
    if _CONSOLE is not None:
        _CONSOLE.input(f"[dim]{message}[/dim]")
        clear_screen()
        return
    input(message)
    clear_screen()


def _prompt_custom_name() -> str:
    clear_screen()
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


def _choose_name(creation_service):
    while True:
        options = [
            "Enter custom name",
            "Use generated name",
            "Help: Creation Reference Library",
            "Cancel character creation",
        ]
        idx = arrow_menu("Character Creation", options, footer_hint="ESC to return to main menu")
        if idx < 0 or idx == 3:
            return False, ""
        if idx == 2:
            _show_creation_reference_library(creation_service)
            continue
        if idx == 1:
            return True, ""

        raw_name = _prompt_custom_name()
        lowered = (raw_name or "").strip().lower()
        if lowered in {"help", "?"}:
            _show_creation_reference_library(creation_service)
            continue
        if lowered in {"esc", "cancel", "q", "quit"}:
            continue
        return True, raw_name


def _render_character_summary(summary) -> None:
    if _CONSOLE is not None and Panel is not None:
        lines = [
            "[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]",
            f"[bold]{summary.name}[/bold], level {summary.level} {summary.class_name}",
            f"Race: {summary.race} (Speed {summary.speed})",
            f"Background: {summary.background}",
            f"Difficulty: {summary.difficulty}",
            f"HP: {summary.hp_current}/{summary.hp_max}",
            f"Abilities: {summary.attributes_line}",
        ]
        if getattr(summary, "subclass_name", ""):
            lines.insert(2, f"Subclass: {summary.subclass_name}")
        if summary.race_traits:
            lines.append(f"Race Traits: {', '.join(summary.race_traits)}")
        if summary.background_features:
            lines.append(f"Background Feature: {', '.join(summary.background_features)}")
        if summary.inventory:
            lines.append(f"Starting Gear: {', '.join(summary.inventory)}")
        lines.append(f"Starting Location: {summary.starting_location_name}")
        lines.append("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
        _CONSOLE.print(
            Panel.fit(
                "\n".join(lines),
                title="[bold yellow]Character Created[/bold yellow]",
                subtitle="[dim]A new name enters the chronicle[/dim]",
                subtitle_align="left",
                border_style=_PANEL_BORDER,
            )
        )
        return

    print(f"You created: {summary.name}, a level {summary.level} {summary.class_name}.")
    if getattr(summary, "subclass_name", ""):
        print(f"Subclass: {summary.subclass_name}")
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
    print(f"Starting Location: {summary.starting_location_name}")


def _show_class_detail(creation_service, chosen_class) -> bool:
    """Return True if player confirms the class (arrow-key driven)."""
    detail = creation_service.class_detail_view(chosen_class)
    options = detail.options
    selected = 0

    while True:
        clear_screen()
        if _CONSOLE is not None and Panel is not None:
            lines = [
                detail.description,
                "",
                f"Primary Ability : {detail.primary_ability}",
                f"Hit Die         : {detail.hit_die}",
                f"Combat Profile  : {detail.combat_profile_line}",
            ]
            if detail.recommended_line:
                lines.append(f"Recommended     : {detail.recommended_line}")
            lines.append("")
            for idx, opt in enumerate(options):
                if idx == selected:
                    lines.append(f"[bold black on yellow] ▶ {opt} [/bold black on yellow]")
                else:
                    lines.append(f"[white]  {opt}[/white]")
            lines.append("")
            lines.append(f"[yellow]{_CREATION_HELP_HINT}[/yellow]")
            lines.append("[dim]Use arrow keys to move, ENTER to select, ESC to cancel.[/dim]")
            _CONSOLE.print(
                Panel.fit(
                    "\n".join(lines),
                    title=f"[bold yellow]{detail.title}[/bold yellow]",
                    border_style=_PANEL_BORDER,
                    subtitle="[dim]↑/↓ Navigate • Enter Confirm • Esc Back[/dim]",
                    subtitle_align="left",
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


def _choose_race(creation_service):
    races = creation_service.list_playable_races()
    while True:
        options = creation_service.race_option_labels() + ["Help: Creation Reference Library"]
        idx = arrow_menu("Choose Your Race", options, footer_hint=_CREATION_HELP_HINT)
        if idx < 0:
            return None
        if idx == len(options) - 1:
            _show_creation_reference_library(creation_service)
            continue
        return races[idx]


def _choose_background(creation_service):
    backgrounds = creation_service.list_backgrounds()
    while True:
        options = creation_service.background_option_labels() + ["Help: Creation Reference Library"]
        idx = arrow_menu("Choose Your Origin", options, footer_hint=_CREATION_HELP_HINT)
        if idx < 0:
            return None
        if idx == len(options) - 1:
            _show_creation_reference_library(creation_service)
            continue
        return backgrounds[idx]


def _choose_subrace(creation_service, race):
    subraces = creation_service.list_subraces_for_race(race=race)
    if not subraces:
        return True, None

    while True:
        options = ["No subrace"] + creation_service.subrace_option_labels(race) + ["Help: Creation Reference Library"]
        idx = arrow_menu("Choose a Subrace", options, footer_hint=_CREATION_HELP_HINT)
        if idx < 0:
            return False, None
        if idx == len(options) - 1:
            _show_creation_reference_library(creation_service)
            continue
        if idx == 0:
            return True, None
        return True, subraces[idx - 1]


def _choose_subclass(creation_service, chosen_class):
    subclass_rows = creation_service.list_subclasses_for_class(
        getattr(chosen_class, "slug", None) or getattr(chosen_class, "name", None)
    )
    if not subclass_rows:
        return True, None

    options = [f"{row.name} — {row.description}" for row in subclass_rows]
    options.append("Back")
    idx = arrow_menu("Choose Your Subclass", options, footer_hint="ESC to return to class selection")
    if idx < 0 or idx == len(options) - 1:
        return False, None
    return True, str(subclass_rows[idx].slug)


def _choose_difficulty(creation_service):
    difficulties = creation_service.list_difficulties()
    while True:
        options = creation_service.difficulty_option_labels() + ["Help: Creation Reference Library"]
        idx = arrow_menu("Difficulty", options, footer_hint=_CREATION_HELP_HINT)
        if idx < 0:
            return None
        if idx == len(options) - 1:
            _show_creation_reference_library(creation_service)
            continue
        return difficulties[idx]


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


def _point_buy_prompt(creation_service, recommended: Dict[str, int]) -> Dict[str, int] | None:
    scores: Dict[str, int] = {ability: 8 for ability in ABILITY_ORDER}
    for ability in ABILITY_ORDER:
        default_val = recommended.get(ability, 8)
        while True:
            clear_screen()
            remaining = 27 - creation_service.point_buy_cost(scores)
            current_line = creation_service.format_attribute_line(scores)
            if _CONSOLE is not None and Panel is not None:
                _CONSOLE.print(
                    Panel.fit(
                        "\n".join(
                            [
                                "[bold]POINT BUY (27 points)[/bold]",
                                f"Current: {current_line}",
                                f"Points remaining: {remaining}",
                                "Need guidance? Enter 'q' to return, then open the Creation Library.",
                            ]
                        ),
                        title=f"[bold yellow]Assign {ability}[/bold yellow]",
                        border_style=_PANEL_BORDER,
                    )
                )
                raw = _CONSOLE.input(
                    f"[bold yellow]Set {ability} (8-15, default {default_val}, 'q' to cancel): [/bold yellow]"
                ).strip()
            else:
                print("POINT BUY (27 points)")
                print(f"Current: {current_line}")
                print(f"Points remaining: {remaining}")
                print("Need guidance? Enter 'q' to return, then open the Creation Library.")
                raw = input(f"Set {ability} (8-15, default {default_val}, 'q' to cancel): ").strip()
            if raw.lower() in {"q", "quit"}:
                return None
            value = default_val if raw == "" else raw
            try:
                proposed = int(value)
            except ValueError:
                if _CONSOLE is not None:
                    _CONSOLE.print("[red]Please enter a number between 8 and 15.[/red]")
                else:
                    print("Please enter a number between 8 and 15.")
                _prompt_enter("Press ENTER to retry...")
                continue

            prior = scores[ability]
            scores[ability] = proposed
            try:
                scores = creation_service.validate_point_buy(scores, pool=27)
            except ValueError as exc:
                scores[ability] = prior
                if _CONSOLE is not None:
                    _CONSOLE.print(f"[red]Invalid choice:[/red] {exc}")
                else:
                    print(f"Invalid choice: {exc}")
                _prompt_enter("Press ENTER to retry...")
                continue
            break
    return scores


def _roll_prompt(creation_service) -> Dict[str, int] | None:
    rolled = roll_attributes_with_animation()
    scores: Dict[str, int] = {}
    for abbr in ATTR_ORDER:
        value = rolled.get(abbr, 8)
        scores[abbr] = value
    return scores


def _choose_abilities(creation_service, chosen_class):
    while True:
        methods = [
            "Class template (standard array)",
            "Point buy (27 points)",
            "Roll 4d6 drop lowest",
            "Help: Creation Reference Library",
        ]
        method = arrow_menu("Ability Scores", methods, footer_hint=_CREATION_HELP_HINT)
        if method < 0:
            return None
        if method == 3:
            _show_creation_reference_library(creation_service)
            continue

        if method == 1:
            recommended = creation_service.standard_array_for_class(chosen_class)
            return _point_buy_prompt(creation_service, recommended)
        if method == 2:
            return _roll_prompt(creation_service)

        return creation_service.standard_array_for_class(chosen_class)


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
        skills = list(game_service.list_granular_skills_intent(character_id) or [])
        options: list[str] = []
        slugs: list[str] = []
        for row in skills:
            if not bool(row.get("eligible_new", False)):
                continue
            slug = str(row.get("slug", "") or "")
            if not slug:
                continue
            label = str(row.get("label", slug)).strip() or slug
            current = int(row.get("current", 0) or 0)
            marker = "[x]" if slug in intent else "[ ]"
            options.append(f"{marker} {label} (current +{current})")
            slugs.append(slug)
        options.extend(["Continue to Spending", "Skip Skill Training"])
        choice = arrow_menu("Creation Skill Intent", options)
        if choice in {-1, len(options) - 1, len(options) - 2}:
            break
        slug = slugs[choice]
        if slug in intent:
            intent = [row for row in intent if row != slug]
        else:
            intent.append(slug)

    game_service.declare_skill_training_intent_intent(character_id, intent)

    while True:
        status = game_service.get_skill_training_status_intent(character_id)
        points = int(status.get("points_available", 0) or 0)
        if points <= 0:
            return

        skills = list(game_service.list_granular_skills_intent(character_id) or [])
        options: list[str] = []
        slugs: list[str] = []
        for row in skills:
            current = int(row.get("current", 0) or 0)
            if current <= 0 and not bool(row.get("eligible_new", False)):
                continue
            slug = str(row.get("slug", "") or "")
            if not slug:
                continue
            label = str(row.get("label", slug)).strip() or slug
            options.append(f"{label} (+{current})")
            slugs.append(slug)
        options.append("Finish")
        pick = arrow_menu(f"Creation Skill Spend ({points} left)", options)
        if pick in {-1, len(options) - 1}:
            return

        result = game_service.spend_skill_proficiency_points_intent(character_id, {slugs[pick]: 1})
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

    while True:  # name loop
        confirmed_name, raw_name = _choose_name(creation_service)
        if not confirmed_name:
            _show_cancelled()
            return None
        name = raw_name

        # Race selection
        while True:
            race = _choose_race(creation_service)
            if race is None:
                # Back to name entry
                break

            selected_subrace = None
            confirmed_subrace, selected_subrace = _choose_subrace(creation_service, race)
            if not confirmed_subrace:
                continue

            classes = creation_service.list_classes()
            if not classes:
                clear_screen()
                print("No classes available.")
                _prompt_enter("Press ENTER to return to the menu...")
                return None

            options = creation_service.list_class_names() + ["Help: Creation Reference Library"]

            # Class selection (with back to race)
            while True:
                idx = arrow_menu("Choose Your Class", options, footer_hint=_CREATION_HELP_HINT)
                if idx < 0:
                    # back to race
                    break
                if idx == len(options) - 1:
                    _show_creation_reference_library(creation_service)
                    continue
                chosen_class = classes[idx]
                if not _show_class_detail(creation_service, chosen_class):
                    continue

                subclass_confirmed, selected_subclass_slug = _choose_subclass(creation_service, chosen_class)
                if not subclass_confirmed:
                    continue

                # Ability + following steps; allow back to class on cancel
                while True:
                    ability_scores = _choose_abilities(creation_service, chosen_class)
                    if ability_scores is None:
                        # back to class selection
                        break

                    # Background (back to abilities)
                    background = _choose_background(creation_service)
                    if background is None:
                        continue

                    # Difficulty (back to background)
                    difficulty = _choose_difficulty(creation_service)
                    if difficulty is None:
                        continue

                    character = creation_service.create_character(
                        name=name,
                        class_index=idx,
                        ability_scores=ability_scores,
                        race=race,
                        subrace=selected_subrace,
                        background=background,
                        difficulty=difficulty,
                        subclass_slug=selected_subclass_slug,
                    )
                    summary = game_service.build_character_creation_summary(character)

                    clear_screen()
                    _render_character_summary(summary)
                    _run_creation_skill_training_flow(game_service, summary.character_id)
                    print("")
                    _prompt_enter("Press ENTER to begin your adventure...")

                    return summary.character_id

                # end ability+ flow
            # end class loop
        # end race loop (back to name)

            # unreachable: we should have returned after creating character
