
import random

from rpg.presentation.menu_controls import arrow_menu, clear_screen

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except Exception:  # pragma: no cover - optional dependency fallback
    Console = None
    Panel = None
    Table = None


_CONSOLE = Console() if Console is not None else None
_BORDER_LOOP = "yellow"
_BORDER_TOWN = "green"
_BORDER_FACTION = "magenta"
_BORDER_SHOP = "bright_yellow"
_BORDER_TRAINING = "cyan"
_BORDER_RUMOUR = "bright_magenta"
_BORDER_QUEST = "magenta"
_BORDER_SOCIAL = "cyan"
_BORDER_CHARACTER = "yellow"
_BORDER_EQUIPMENT = "green"


def _threat_descriptor(threat_level) -> str:
    if threat_level is None:
        return "Unknown"
    try:
        normalized = int(threat_level)
    except (TypeError, ValueError):
        return "Unknown"
    if normalized <= 1:
        return "Safe"
    if normalized == 2:
        return "Guarded"
    if normalized == 3:
        return "Frontier"
    if normalized == 4:
        return "Perilous"
    return "Lawless"


def _ornate_title(title: str, panel_key: str = "") -> str:
    core = str(title or "").strip() or "Panel"
    return f"[bold yellow]{core}[/bold yellow]"


def _panel_subtitle(panel_key: str) -> str:
    lookup = {
        "loop": "[dim]Chronicle of the current day[/dim]",
        "town": "[dim]Safe walls, shifting loyalties[/dim]",
        "factions": "[dim]Influence ledger[/dim]",
        "shop": "[dim]Wares and weighted coin[/dim]",
        "training": "[dim]Drills, rites, and discipline[/dim]",
        "rumours": "[dim]Whispers gathered at dusk[/dim]",
        "quests": "[dim]Contracts sealed in ink[/dim]",
        "npc": "[dim]Temperament and intent[/dim]",
        "social": "[dim]Words carry consequence[/dim]",
        "character": "[dim]Record of your legend[/dim]",
        "equipment": "[dim]Steel, mail, and charms[/dim]",
        "inventory": "[dim]Pack and provisions[/dim]",
    }
    return lookup.get(str(panel_key), "[dim]Adventurer's ledger[/dim]")


def _prompt_continue(message: str = "Press ENTER to continue...") -> None:
    if _CONSOLE is not None:
        _CONSOLE.input(f"[dim]{message}[/dim]")
        clear_screen()
        return
    input(message)
    clear_screen()


def _render_message_panel(
    title: str,
    lines: list[str],
    *,
    border_style: str = _BORDER_LOOP,
    panel_key: str = "loop",
) -> None:
    rows = [str(line) for line in lines if str(line).strip()]
    if _CONSOLE is not None and Panel is not None:
        body = "\n".join(rows) if rows else "No updates."
        _CONSOLE.print(
            Panel.fit(
                body,
                title=_ornate_title(title, panel_key),
                subtitle=_panel_subtitle(panel_key),
                subtitle_align="left",
                border_style=border_style,
            )
        )
        return

    print(f"=== {title} ===")
    for row in rows:
        print(row)


def _render_loop_header(context, view, descriptor: str, diff_label: str, world_line: str, party_lines: list[str] | None = None) -> None:
    party_lines = [str(line) for line in list(party_lines or []) if str(line).strip()]
    if _CONSOLE is not None and Panel is not None and Table is not None:
        header = Table.grid(padding=(0, 1))
        header.add_column(style="bold yellow", justify="right")
        header.add_column(style="white")
        header.add_row("Location", context.current_location_name)
        header.add_row("World", world_line)
        header.add_row("Adventurer", f"{view.name} the {descriptor}")
        header.add_row("Difficulty", diff_label.title())
        header.add_row("HP", f"{view.hp_current}/{view.hp_max}")
        if party_lines:
            header.add_row("Party", "\n".join(f"- {line}" for line in party_lines))
        _CONSOLE.print(
            Panel.fit(
                header,
                title=_ornate_title(context.title, "loop"),
                subtitle=_panel_subtitle("loop"),
                subtitle_align="left",
                border_style=_BORDER_LOOP,
            )
        )
        return

    print(f"=== {context.title} ===")
    print(f"{world_line}")
    print(f"Location: {context.current_location_name}")
    print(f"{view.name} the {descriptor} | Difficulty: {diff_label.title()} | HP: {view.hp_current}/{view.hp_max}")
    if party_lines:
        print("Party:")
        for line in party_lines:
            print(f"- {line}")


def _render_town_header(town_view) -> None:
    day = town_view.day if town_view.day is not None else "?"
    threat = _threat_descriptor(town_view.threat_level)
    location_name = str(getattr(town_view, "location_name", "") or "Town")
    consequences = list(town_view.consequences or [])

    if _CONSOLE is not None and Panel is not None and Table is not None:
        header = Table.grid(padding=(0, 1))
        header.add_column(style="bold yellow", justify="right")
        header.add_column(style="white")
        header.add_row("Location", location_name)
        header.add_row("Day", str(day))
        header.add_row("Threat", str(threat))
        if getattr(town_view, "district_tag", ""):
            header.add_row("District", str(town_view.district_tag))
        if getattr(town_view, "landmark_tag", ""):
            header.add_row("Landmark", str(town_view.landmark_tag))
        if getattr(town_view, "active_prep_summary", ""):
            header.add_row("Travel Prep", str(town_view.active_prep_summary))
        if consequences:
            header.add_row("Recent", "\n".join(f"- {line}" for line in consequences))
        _CONSOLE.print(
            Panel.fit(
                header,
                title=_ornate_title("Town", "town"),
                subtitle=_panel_subtitle("town"),
                subtitle_align="left",
                border_style=_BORDER_TOWN,
            )
        )
        return

    print(f"=== {location_name} ===")
    print(f"Day {day} | Threat: {threat}")
    if getattr(town_view, "district_tag", ""):
        print(f"District: {town_view.district_tag}")
    if getattr(town_view, "landmark_tag", ""):
        print(f"Landmark: {town_view.landmark_tag}")
    if getattr(town_view, "active_prep_summary", ""):
        print(f"Travel Prep: {town_view.active_prep_summary}")
    if consequences:
        print("Recent consequences:")
        for line in consequences:
            print(f"- {line}")


def _render_faction_standings(standings, descriptions=None, empty_state_hint: str = "") -> None:
    clear_screen()
    descriptions = descriptions or {}
    if _CONSOLE is not None and Panel is not None and Table is not None:
        if not standings:
            _CONSOLE.print(
                Panel.fit(
                    empty_state_hint or "No standings tracked yet.",
                    title=_ornate_title("Faction Standings", "factions"),
                    subtitle=_panel_subtitle("factions"),
                    subtitle_align="left",
                    border_style=_BORDER_FACTION,
                )
            )
            return
        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Faction")
        table.add_column("Score", justify="right")
        table.add_column("Description")
        for faction_id, score in standings.items():
            table.add_row(str(faction_id), str(score), str(descriptions.get(str(faction_id), "")))
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title("Faction Standings", "factions"),
                subtitle=_panel_subtitle("factions"),
                subtitle_align="left",
                border_style=_BORDER_FACTION,
            )
        )
        return

    print("=== Faction Standings ===")
    if not standings:
        print(empty_state_hint or "No standings tracked yet.")
    else:
        for faction_id, score in standings.items():
            description = str(descriptions.get(str(faction_id), "") or "").strip()
            if description:
                print(f"- {faction_id}: {score} — {description}")
            else:
                print(f"- {faction_id}: {score}")


def _render_shop_header(shop, location_name: str = "Town") -> None:
    if _CONSOLE is not None and Panel is not None and Table is not None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold yellow", justify="right")
        table.add_column(style="white")
        table.add_row("Gold", str(shop.gold))
        table.add_row("Pricing", shop.price_modifier_label)
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title(f"Shop — {location_name}", "shop"),
                subtitle=_panel_subtitle("shop"),
                subtitle_align="left",
                border_style=_BORDER_SHOP,
            )
        )
        return

    print(f"=== Shop — {location_name} ===")
    print(f"Gold: {shop.gold} | Pricing: {shop.price_modifier_label}")


def _render_training_header(training, location_name: str = "Town") -> None:
    if _CONSOLE is not None and Panel is not None and Table is not None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold yellow", justify="right")
        table.add_column(style="white")
        table.add_row("Gold", str(training.gold))
        table.add_row("Options", str(len(training.options)))
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title(f"Training — {location_name}", "training"),
                subtitle=_panel_subtitle("training"),
                subtitle_align="left",
                border_style=_BORDER_TRAINING,
            )
        )
        return

    print(f"=== Training — {location_name} ===")
    print(f"Gold: {training.gold}")


def _render_travel_prep_header(prep_view) -> None:
    if _CONSOLE is not None and Panel is not None and Table is not None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold yellow", justify="right")
        table.add_column(style="white")
        table.add_row("Gold", str(prep_view.gold))
        if prep_view.active_summary:
            table.add_row("Active", str(prep_view.active_summary))
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title("Travel Prep", "town"),
                subtitle=_panel_subtitle("town"),
                subtitle_align="left",
                border_style=_BORDER_TOWN,
            )
        )
        return

    print("=== Travel Prep ===")
    print(f"Gold: {prep_view.gold}")
    if prep_view.active_summary:
        print(f"Active for next journey: {prep_view.active_summary}")


def _render_rumour_board_header(board, location_name: str = "Town") -> None:
    day = board.day if board.day is not None else "?"
    item_count = len(board.items or [])
    if _CONSOLE is not None and Panel is not None and Table is not None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold yellow", justify="right")
        table.add_column(style="white")
        table.add_row("Day", str(day))
        table.add_row("Rumours", str(item_count))
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title(f"Rumour Board — {location_name}", "rumours"),
                subtitle=_panel_subtitle("rumours"),
                subtitle_align="left",
                border_style=_BORDER_RUMOUR,
            )
        )
        return

    print(f"=== Rumour Board — {location_name} ===")
    print(f"Day {day}")


def _render_quest_board_header(board, location_name: str = "Town") -> None:
    quest_count = len(board.quests or [])
    if _CONSOLE is not None and Panel is not None and Table is not None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold yellow", justify="right")
        table.add_column(style="white")
        table.add_row("Posted Quests", str(quest_count))
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title(f"Quest Board — {location_name}", "quests"),
                subtitle=_panel_subtitle("quests"),
                subtitle_align="left",
                border_style=_BORDER_QUEST,
            )
        )
        return

    print(f"=== Quest Board — {location_name} ===")


def _render_npc_interaction_header(interaction) -> None:
    if _CONSOLE is not None and Panel is not None and Table is not None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold yellow", justify="right")
        table.add_column(style="white")
        table.add_row("Name", interaction.npc_name)
        table.add_row("Role", interaction.role)
        table.add_row("Relationship", str(interaction.relationship))
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title("NPC Interaction", "npc"),
                subtitle=_panel_subtitle("npc"),
                subtitle_align="left",
                border_style=_BORDER_SOCIAL,
            )
        )
        return

    print("=== NPC Interaction ===")
    print(f"{interaction.npc_name} ({interaction.role})")
    print(f"Relationship: {interaction.relationship}")


def _render_social_result_header(outcome) -> None:
    if _CONSOLE is not None and Panel is not None and Table is not None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold yellow", justify="right")
        table.add_column(style="white")
        table.add_row("NPC", outcome.npc_name)
        table.add_row("Approach", outcome.approach)
        table.add_row("Outcome", "Success" if outcome.success else "Failure")
        table.add_row("Roll", f"{outcome.roll_total} vs DC {outcome.target_dc}")
        table.add_row("Relationship", f"{outcome.relationship_before} → {outcome.relationship_after}")
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title("Social Result", "social"),
                subtitle=_panel_subtitle("social"),
                subtitle_align="left",
                border_style=_BORDER_SOCIAL,
            )
        )
        return

    print("=== Social Result ===")


def _render_character_sheet(sheet) -> None:
    clear_screen()
    if _CONSOLE is not None and Panel is not None and Table is not None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold cyan", justify="right")
        table.add_column(style="white")
        table.add_row("Name", sheet.name)
        table.add_row(
            "Race/Class",
            f"{(sheet.race or 'Unknown')} {(sheet.class_name or 'Adventurer').title()}",
        )
        table.add_row("Level", str(sheet.level))
        table.add_row("XP", f"{sheet.xp}/{sheet.next_level_xp}")
        table.add_row("To Next", str(sheet.xp_to_next_level))
        table.add_row("HP", f"{sheet.hp_current}/{sheet.hp_max}")
        table.add_row("Difficulty", str(sheet.difficulty).title())
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title("Character", "character"),
                subtitle=_panel_subtitle("character"),
                subtitle_align="left",
                border_style=_BORDER_CHARACTER,
            )
        )
        return

    print("=== Character ===")
    print(f"Name: {sheet.name}")
    print(f"Race/Class: {(sheet.race or 'Unknown')} {(sheet.class_name or 'Adventurer').title()}")
    print(f"Level: {sheet.level}")
    print(f"XP: {sheet.xp}/{sheet.next_level_xp} (to next: {sheet.xp_to_next_level})")
    print(f"HP: {sheet.hp_current}/{sheet.hp_max}")
    print(f"Difficulty: {str(sheet.difficulty).title()}")


def _render_quest_journal(journal) -> None:
    clear_screen()
    if _CONSOLE is not None and Panel is not None and Table is not None:
        if not journal.sections:
            _CONSOLE.print(
                Panel.fit(
                    journal.empty_state_hint or "No quests tracked yet.",
                    title=_ornate_title("Quest Journal", "quests"),
                    subtitle=_panel_subtitle("quests"),
                    subtitle_align="left",
                    border_style=_BORDER_QUEST,
                )
            )
            return
        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Section")
        table.add_column("Quest")
        table.add_column("Objective")
        table.add_column("Urgency")
        table.add_column("Rewards", justify="right")
        for section in journal.sections:
            for quest in section.quests:
                table.add_row(
                    section.title,
                    quest.title,
                    quest.objective_summary or f"{quest.progress}/{quest.target}",
                    quest.urgency_label,
                    f"{quest.reward_xp} XP, {quest.reward_money}g",
                )
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title("Quest Journal", "quests"),
                subtitle=_panel_subtitle("quests"),
                subtitle_align="left",
                border_style=_BORDER_QUEST,
            )
        )
        return

    print("=== Quest Journal ===")
    if not journal.sections:
        print(journal.empty_state_hint or "No quests tracked yet.")
        return
    for section in journal.sections:
        print(f"{section.title}:")
        for quest in section.quests:
            urgency = f" | {quest.urgency_label}" if quest.urgency_label else ""
            print(
                f"- {quest.title} [{quest.status}] {quest.objective_summary or f'({quest.progress}/{quest.target})'}{urgency} "
                f"Reward {quest.reward_xp} XP, {quest.reward_money}g"
            )
        print("")


def _render_equipment_view(equipment_view) -> None:
    clear_screen()
    equipped = dict(getattr(equipment_view, "equipped_slots", {}) or {})
    inventory_rows = list(getattr(equipment_view, "inventory_items", []) or [])

    if _CONSOLE is not None and Panel is not None and Table is not None:
        header = Table.grid(padding=(0, 1))
        header.add_column(style="bold yellow", justify="right")
        header.add_column(style="white")
        for slot in ("weapon", "armor", "trinket"):
            header.add_row(slot.title(), equipped.get(slot, "(empty)"))
        _CONSOLE.print(
            Panel.fit(
                header,
                title=_ornate_title("Equipment", "equipment"),
                subtitle=_panel_subtitle("equipment"),
                subtitle_align="left",
                border_style=_BORDER_EQUIPMENT,
            )
        )

        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Item")
        table.add_column("Slot")
        table.add_column("State")
        for row in inventory_rows:
            slot = row.slot or "-"
            state = "Equipped" if row.equipped else ("Equipable" if row.equipable else "Carry")
            table.add_row(row.name, slot, state)
        _CONSOLE.print(
            Panel.fit(
                table,
                title=_ornate_title("Inventory", "inventory"),
                subtitle=_panel_subtitle("inventory"),
                subtitle_align="left",
                border_style=_BORDER_EQUIPMENT,
            )
        )
        return

    print("=== Equipment ===")
    for slot in ("weapon", "armor", "trinket"):
        print(f"{slot.title()}: {equipped.get(slot, '(empty)')}")
    print("")
    print("Inventory:")
    for row in inventory_rows:
        slot = row.slot or "-"
        state = "[equipped]" if row.equipped else ("[equipable]" if row.equipable else "")
        print(f"- {row.name} ({slot}) {state}".rstrip())


def _run_party_management(game_service, character_id: int, character_name: str) -> None:
    while True:
        rows = list(game_service.get_party_management_intent(character_id) or [])
        active_count, max_count = game_service.get_party_capacity_intent(character_id)
        capacity_label = f"Active companions: {active_count}/{max_count}"
        if active_count >= max_count:
            capacity_label = f"{capacity_label} (Full)"
        lines = [capacity_label, ""]
        options = []
        for row in rows:
            unlocked = bool(row.get("unlocked", False))
            if unlocked:
                status = "Active" if bool(row.get("active")) else "Reserve"
                lane = str(row.get("lane", "auto") or "auto").title()
                text = f"{row.get('name', 'Companion')} [{status}] — {row.get('status', '')} — Lane {lane}"
            else:
                recruitable = bool(row.get("recruitable", False))
                lock_state = "Recruitable" if recruitable else "Locked"
                gate_note = str(row.get("gate_note", "") or "").strip()
                text = f"{row.get('name', 'Companion')} [{lock_state}]"
                if gate_note:
                    text = f"{text} — {gate_note}"
            lines.append(text)
            options.append(text)
        if not options:
            clear_screen()
            _render_message_panel(
                "Party",
                ["No companions are available right now."],
                border_style=_BORDER_CHARACTER,
                panel_key="character",
            )
            _prompt_continue()
            return

        clear_screen()
        _render_message_panel("Party", lines, border_style=_BORDER_CHARACTER, panel_key="character")
        options.append("Back")
        selected = arrow_menu(f"Party — {character_name}", options)
        if selected in {-1, len(options) - 1}:
            return

        chosen = rows[selected]
        companion_id = str(chosen.get("companion_id", "") or "")
        companion_name = str(chosen.get("name", "Companion") or "Companion")
        active = bool(chosen.get("active"))
        unlocked = bool(chosen.get("unlocked", False))

        if not unlocked:
            recruitable = bool(chosen.get("recruitable", False))
            recruit_label = "Recruit" if recruitable else "Recruit (Locked)"
            sub_choice = arrow_menu(f"Party Member — {companion_name}", [recruit_label, "Back"])
            if sub_choice in {-1, 1}:
                continue
            result = game_service.recruit_companion_intent(character_id, companion_id)
            clear_screen()
            _render_message_panel("Party", list(result.messages or []), border_style=_BORDER_CHARACTER, panel_key="character")
            _prompt_continue()
            continue

        while True:
            lane = str(chosen.get("lane", "auto") or "auto").lower()
            lane_options = ["Auto", "Vanguard", "Rearguard"]
            lane_idx = 0
            if lane == "vanguard":
                lane_idx = 1
            elif lane == "rearguard":
                lane_idx = 2

            active_count, max_count = game_service.get_party_capacity_intent(character_id)
            can_activate = active or active_count < max_count
            activate_label = "Deactivate" if active else ("Activate" if can_activate else "Activate (Party Full)")

            sub_options = [
                activate_label,
                f"Lane: {lane_options[lane_idx]}",
                "Back",
            ]
            sub_choice = arrow_menu(f"Party Member — {companion_name}", sub_options)
            if sub_choice in {-1, 2}:
                break
            if sub_choice == 0:
                if not active and not can_activate:
                    clear_screen()
                    _render_message_panel(
                        "Party",
                        [f"Party is full ({active_count}/{max_count}). Deactivate a companion first."],
                        border_style=_BORDER_CHARACTER,
                        panel_key="character",
                    )
                    _prompt_continue()
                    continue
                result = game_service.set_party_companion_active_intent(character_id, companion_id, not active)
                clear_screen()
                _render_message_panel("Party", list(result.messages or []), border_style=_BORDER_CHARACTER, panel_key="character")
                _prompt_continue()
                break

            next_lane = lane_options[(lane_idx + 1) % len(lane_options)].lower()
            result = game_service.set_party_companion_lane_intent(character_id, companion_id, next_lane)
            clear_screen()
            _render_message_panel("Party", list(result.messages or []), border_style=_BORDER_CHARACTER, panel_key="character")
            _prompt_continue()
            break


def _render_combat_round(round_view) -> None:
    clear_screen()
    if _CONSOLE is not None and Panel is not None and Table is not None:
        summary = Table.grid(padding=(0, 1))
        summary.add_column(style="bold yellow", justify="right")
        summary.add_column(style="white")
        summary.add_row("Round", str(round_view.round_number))
        summary.add_row("Distance", str(round_view.scene.distance))
        summary.add_row("Terrain", str(round_view.scene.terrain))
        summary.add_row("Surprise", str(round_view.scene.surprise))
        _CONSOLE.print(
            Panel.fit(
                summary,
                title=_ornate_title("Combat", "loop"),
                subtitle=_panel_subtitle("loop"),
                subtitle_align="left",
                border_style=_BORDER_LOOP,
            )
        )

        combatants = Table(show_header=True, header_style="bold yellow")
        combatants.add_column("Combatant")
        combatants.add_column("HP", justify="right")
        combatants.add_column("AC", justify="right")
        combatants.add_column("Offense")
        combatants.add_column("Status")
        combatants.add_row(
            "You",
            f"{round_view.player.hp_current}/{round_view.player.hp_max}",
            str(round_view.player.armor_class),
            f"+{round_view.player.attack_bonus} | Slots {round_view.player.spell_slots_current}",
            f"Rage: {round_view.player.rage_label} | Sneak: {round_view.player.sneak_ready} | {round_view.player.conditions}",
        )
        combatants.add_row(
            str(round_view.enemy.name),
            f"{round_view.enemy.hp_current}/{round_view.enemy.hp_max}",
            str(round_view.enemy.armor_class),
            "-",
            f"Intent: {round_view.enemy.intent}",
        )
        _CONSOLE.print(
            Panel.fit(
                combatants,
                title=_ornate_title("Round State", "loop"),
                subtitle="[dim]Choose your next action[/dim]",
                subtitle_align="left",
                border_style=_BORDER_LOOP,
            )
        )
        return

    print("=== Combat ===")
    print(f"Round {round_view.round_number}")
    print(f"Scene: Distance {round_view.scene.distance} | Terrain {round_view.scene.terrain}")
    print(f"Surprise: {round_view.scene.surprise}")
    print("--- You ---")
    print(
        f"HP {round_view.player.hp_current}/{round_view.player.hp_max} "
        f"| AC {round_view.player.armor_class} "
        f"| Attack +{round_view.player.attack_bonus} "
        f"| Slots {round_view.player.spell_slots_current}"
    )
    print(f"Rage: {round_view.player.rage_label} | Sneak Ready: {round_view.player.sneak_ready}")
    print(f"Conditions: {round_view.player.conditions}")
    print("")
    print(f"--- {round_view.enemy.name} ---")
    print(
        f"HP {round_view.enemy.hp_current}/{round_view.enemy.hp_max} "
        f"| AC {round_view.enemy.armor_class}"
    )
    print(f"Intent: {round_view.enemy.intent}")
    print("")


def run_game_loop(game_service, character_id: int):
    while True:
        try:
            view = game_service.get_game_loop_view(character_id)
            context = game_service.get_location_context_intent(character_id)
        except Exception:
            clear_screen()
            _render_message_panel(
                "Character Missing",
                ["Your character could not be found. Returning to the menu."],
                border_style=_BORDER_CHARACTER,
                panel_key="character",
            )
            _prompt_continue()
            break

        pending_level_up = None
        try:
            pending_level_up = game_service.get_level_up_pending_intent(character_id)
        except Exception:
            pending_level_up = None
        if pending_level_up is not None:
            clear_screen()
            _render_message_panel(
                "Level Up",
                [
                    pending_level_up.summary or "Your experience allows a level up.",
                    f"Level {pending_level_up.current_level} -> {pending_level_up.next_level}",
                    f"XP {pending_level_up.xp_current}/{pending_level_up.xp_required}",
                ],
                border_style=_BORDER_CHARACTER,
                panel_key="character",
            )
            choices = [str(choice).title() for choice in list(pending_level_up.growth_choices or [])]
            choices.append("Keep Adventuring")
            selection = arrow_menu("Choose Growth", choices)
            if selection not in {-1, len(choices) - 1}:
                chosen_kind = str(pending_level_up.growth_choices[selection])
                result = game_service.submit_level_up_choice_intent(character_id, chosen_kind)
                clear_screen()
                _render_message_panel(
                    "Level Up Result",
                    list(result.messages or []),
                    border_style=_BORDER_CHARACTER,
                    panel_key="character",
                )
                _prompt_continue()
                continue

        clear_screen()
        title_bits = []
        if view.race:
            title_bits.append(view.race)
        if view.class_name:
            title_bits.append(view.class_name.title())
        descriptor = " ".join(title_bits) if title_bits else "Adventurer"
        diff_label = view.difficulty or "normal"
        threat_label = _threat_descriptor(view.threat_level)
        world_line = (
            f"Day {view.world_turn} – Threat: {threat_label}"
            if view.world_turn is not None
            else "Day ? – Threat: Unknown"
        )
        _render_loop_header(
            context=context,
            view=view,
            descriptor=descriptor,
            diff_label=diff_label,
            world_line=world_line,
            party_lines=game_service.get_party_status_intent(character_id),
        )
        recovery_note = game_service.get_recovery_status_intent(character_id)
        if recovery_note:
            if _CONSOLE is not None:
                _CONSOLE.print(f"[dim]{recovery_note}[/dim]")
            else:
                print(recovery_note)
        choice = arrow_menu(f"{context.current_location_name} — Actions", ["Act", "Travel", "Rest", "Character", "Quit"])

        if choice == 0:
            if context.location_type == "town":
                _run_town(game_service, character_id)
            else:
                _run_explore(game_service, character_id)

        elif choice == 1:
            destinations = game_service.get_travel_destinations_intent(character_id)
            if destinations:
                options = [f"{row.name} ({row.preview})" for row in destinations] + ["Back"]
                selected = arrow_menu(context.travel_label, options)
                if selected in {-1, len(options) - 1}:
                    continue
                destination = destinations[selected]
                mode = _choose_travel_mode(context.current_location_name)
                if mode is None:
                    continue
                result = game_service.travel_intent(character_id, destination_id=destination.location_id, travel_mode=mode)
            else:
                result = game_service.travel_intent(character_id)
            messages = result.messages if result.messages else ["You travel onward."]
            clear_screen()
            _render_message_panel("Travel", messages, border_style=_BORDER_LOOP, panel_key="loop")
            _prompt_continue()

        elif choice == 2:
            try:
                result = game_service.rest_intent(character_id)
                fallback_message = "You rest and feel restored." if context.location_type == "town" else "You make camp and recover."
                message = result.messages[0] if result.messages else fallback_message
            except Exception:
                message = "You rest and feel restored." if context.location_type == "town" else "You make camp and recover."
            clear_screen()
            _render_message_panel("Rest", [message], border_style=_BORDER_LOOP, panel_key="loop")
            _prompt_continue()

        elif choice == 3:
            while True:
                char_choice = arrow_menu(f"Character — {view.name}", ["View Sheet", "Quest Journal", "Equipment", "Party", "Companion Leads", "Back"])
                if char_choice in {-1, 5}:
                    break
                if char_choice == 0:
                    character_sheet = game_service.get_character_sheet_intent(character_id)
                    _render_character_sheet(character_sheet)
                    _prompt_continue()
                    continue
                if char_choice == 1:
                    journal = game_service.get_quest_journal_intent(character_id)
                    _render_quest_journal(journal)
                    _prompt_continue()
                    continue
                if char_choice == 3:
                    _run_party_management(game_service, character_id, view.name)
                    continue
                if char_choice == 4:
                    _run_companion_leads(game_service, character_id)
                    continue

                while True:
                    equipment_view = game_service.get_equipment_view_intent(character_id)
                    _render_equipment_view(equipment_view)
                    equipable_rows = [row for row in equipment_view.inventory_items if row.equipable and not row.equipped]
                    equipped_slots = {
                        slot: item
                        for slot, item in dict(getattr(equipment_view, "equipped_slots", {}) or {}).items()
                        if str(item).strip()
                    }
                    inventory_rows = list(getattr(equipment_view, "inventory_items", []) or [])

                    actions: list[tuple[str, str]] = []
                    options: list[str] = []
                    for row in equipable_rows:
                        options.append(f"Equip {row.name} ({row.slot})")
                        actions.append(("equip", row.name))
                    for slot, item in equipped_slots.items():
                        options.append(f"Unequip {item} ({slot})")
                        actions.append(("unequip", slot))
                    for row in inventory_rows:
                        options.append(f"Drop {row.name}")
                        actions.append(("drop", row.name))
                    options.append("Back")

                    selected = arrow_menu(f"Equipment — {view.name}", options)
                    if selected in {-1, len(options) - 1}:
                        break

                    action, payload = actions[selected]
                    if action == "equip":
                        result = game_service.equip_inventory_item_intent(character_id, payload)
                    elif action == "unequip":
                        result = game_service.unequip_slot_intent(character_id, payload)
                    else:
                        result = game_service.drop_inventory_item_intent(character_id, payload)

                    clear_screen()
                    _render_message_panel(
                        "Equipment",
                        list(result.messages or []),
                        border_style=_BORDER_EQUIPMENT,
                        panel_key="equipment",
                    )
                    _prompt_continue()

        elif choice == 4 or choice == -1:
            break


def _run_town(game_service, character_id: int):
    while True:
        town_view = game_service.get_town_view_intent(character_id)
        clear_screen()
        _render_town_header(town_view)

        town_name = str(getattr(town_view, "location_name", "") or "Town")
        choice = arrow_menu(
            f"Town Options — {town_name}",
            ["Talk", "Quest Board", "Rumour Board", "Shop", "Training", "Travel Prep", "View Factions", "Leave Town"],
        )
        if choice in {-1, 7}:
            return
        if choice == 1:
            _run_quest_board(game_service, character_id)
            continue
        if choice == 2:
            _run_rumour_board(game_service, character_id)
            continue
        if choice == 3:
            _run_shop(game_service, character_id)
            continue
        if choice == 4:
            _run_training(game_service, character_id)
            continue
        if choice == 5:
            _run_travel_prep(game_service, character_id)
            continue
        if choice == 6:
            standings_view = game_service.get_faction_standings_view_intent(character_id)
            _render_faction_standings(
                standings_view.standings,
                standings_view.descriptions,
                standings_view.empty_state_hint,
            )
            _prompt_continue()
            continue

        npc_options = [
            f"{npc.name} ({npc.role}) [{npc.temperament}] relationship {npc.relationship}"
            for npc in town_view.npcs
        ]
        npc_options.append("Back")
        npc_choice = arrow_menu("Talk To Who?", npc_options)
        if npc_choice in {-1, len(npc_options) - 1}:
            continue

        selected_npc = town_view.npcs[npc_choice]
        interaction = game_service.get_npc_interaction_intent(character_id, selected_npc.id)

        clear_screen()
        _render_npc_interaction_header(interaction)
        _render_message_panel(
            "NPC Greeting",
            [interaction.greeting],
            border_style=_BORDER_SOCIAL,
            panel_key="npc",
        )
        approach_choice = arrow_menu(
            "Choose Approach",
            interaction.approaches + ["Back"],
        )
        if approach_choice in {-1, len(interaction.approaches)}:
            continue

        approach = interaction.approaches[approach_choice]
        outcome = game_service.submit_social_approach_intent(character_id, selected_npc.id, approach)
        clear_screen()
        _render_social_result_header(outcome)
        _render_message_panel("Social Outcome", list(outcome.messages or []), border_style=_BORDER_SOCIAL, panel_key="social")
        _prompt_continue()


def _run_companion_leads(game_service, character_id: int) -> None:
    lines = list(game_service.get_companion_leads_intent(character_id) or [])
    if not lines:
        lines = ["No companion intelligence has been recorded yet."]
    clear_screen()
    _render_message_panel("Companion Leads", lines, border_style=_BORDER_CHARACTER, panel_key="character")
    _prompt_continue()


def _run_rumour_board(game_service, character_id: int):
    board = game_service.get_rumour_board_intent(character_id)
    context = game_service.get_location_context_intent(character_id)
    town_name = context.current_location_name or "Town"
    clear_screen()
    _render_rumour_board_header(board, town_name)
    lines: list[str] = []
    if not board.items:
        lines.append(board.empty_state_hint or "No useful rumours today.")
    else:
        for item in board.items:
            lines.append(f"- {item.text}")
            lines.append(f"  Source: {item.source} | Confidence: {item.confidence}")
    _render_message_panel("Rumours", lines, border_style=_BORDER_RUMOUR, panel_key="rumours")
    _prompt_continue()


def _run_shop(game_service, character_id: int):
    while True:
        context = game_service.get_location_context_intent(character_id)
        town_name = context.current_location_name or "Town"
        mode = arrow_menu(f"Shop — {town_name}", ["Buy", "Sell", "Back"])
        if mode in {-1, 2}:
            return

        if mode == 1:
            sell_view = game_service.get_sell_inventory_view_intent(character_id)
            clear_screen()
            _render_message_panel("Sell Items", [f"Gold: {sell_view.gold}"], border_style=_BORDER_SHOP, panel_key="shop")
            if not sell_view.items:
                _render_message_panel(
                    "Sell Items",
                    [sell_view.empty_state_hint or "No items available to sell."],
                    border_style=_BORDER_SHOP,
                    panel_key="shop",
                )
                _prompt_continue()
                continue

            options = []
            for row in sell_view.items:
                marker = " [equipped]" if row.equipped else ""
                options.append(f"Sell {row.name} for {row.price}g{marker}")
            options.append("Back")
            choice = arrow_menu(f"Sell — {town_name}", options)
            if choice in {-1, len(options) - 1}:
                continue

            selected = sell_view.items[choice]
            result = game_service.sell_inventory_item_intent(character_id, selected.name)
            clear_screen()
            _render_message_panel("Shop Result", list(result.messages or []), border_style=_BORDER_SHOP, panel_key="shop")
            _prompt_continue()
            continue

        shop = game_service.get_shop_view_intent(character_id)
        clear_screen()
        _render_shop_header(shop, town_name)

        options = []
        for item in shop.items:
            state = "Available" if item.can_buy else (item.availability_note or "Unavailable")
            options.append(f"{item.name} - {item.price}g [{state}]")
        options.append("Back")

        choice = arrow_menu(f"Buy — {town_name}", options)
        if choice in {-1, len(options) - 1}:
            return

        selected = shop.items[choice]
        result = game_service.buy_shop_item_intent(character_id, selected.item_id)
        clear_screen()
        _render_message_panel("Shop Result", list(result.messages or []), border_style=_BORDER_SHOP, panel_key="shop")
        _prompt_continue()


def _run_training(game_service, character_id: int):
    while True:
        training = game_service.get_training_view_intent(character_id)
        context = game_service.get_location_context_intent(character_id)
        town_name = context.current_location_name or "Town"
        clear_screen()
        _render_training_header(training, town_name)

        options = []
        for row in training.options:
            if row.unlocked:
                state = "Completed"
            elif row.availability_note:
                state = row.availability_note
            elif row.can_buy:
                state = "Available"
            else:
                state = "Insufficient gold"
            options.append(f"{row.title} - {row.cost}g [{state}]")
        options.append("Back")

        choice = arrow_menu(f"Training — {town_name}", options)
        if choice in {-1, len(options) - 1}:
            return

        selected = training.options[choice]
        result = game_service.purchase_training_intent(character_id, selected.training_id)
        clear_screen()
        _render_message_panel("Training Result", list(result.messages or []), border_style=_BORDER_TRAINING, panel_key="training")
        _prompt_continue()


def _run_travel_prep(game_service, character_id: int):
    while True:
        prep_view = game_service.get_travel_prep_view_intent(character_id)
        context = game_service.get_location_context_intent(character_id)
        town_name = context.current_location_name or "Town"
        clear_screen()
        _render_travel_prep_header(prep_view)

        options = []
        for row in prep_view.options:
            if row.active:
                state = "Active"
            elif row.availability_note:
                state = row.availability_note
            elif row.can_buy:
                state = "Available"
            else:
                state = "Unavailable"
            options.append(f"{row.title} - {row.price}g [{state}]")
        options.append("Back")

        choice = arrow_menu(f"Travel Prep — {town_name}", options)
        if choice in {-1, len(options) - 1}:
            return

        selected = prep_view.options[choice]
        result = game_service.purchase_travel_prep_intent(character_id, selected.prep_id)
        clear_screen()
        _render_message_panel("TRAVEL PREP RESULT", list(result.messages or []), border_style=_BORDER_TOWN, panel_key="town")
        _prompt_continue()


def _run_quest_board(game_service, character_id: int):
    while True:
        board = game_service.get_quest_board_intent(character_id)
        context = game_service.get_location_context_intent(character_id)
        town_name = context.current_location_name or "Town"
        clear_screen()
        _render_quest_board_header(board, town_name)
        if not board.quests:
            _render_message_panel(
                "Quest Board",
                [board.empty_state_hint or "No quest postings yet. Check back tomorrow."],
                border_style=_BORDER_QUEST,
                panel_key="quests",
            )
            _prompt_continue("Press ENTER to return...")
            return

        options = [
            f"{quest.title} [{quest.status}] {quest.objective_summary or f'({quest.progress}/{quest.target})'}"
            f"{(' - ' + quest.urgency_label) if quest.urgency_label else ''} "
            f"Reward {quest.reward_xp} XP, {quest.reward_money}g"
            for quest in board.quests
        ]
        options.append("Back")
        selected = arrow_menu(f"Quest Board — {town_name}", options)
        if selected in {-1, len(options) - 1}:
            return

        quest = board.quests[selected]
        if quest.status == "available":
            result = game_service.accept_quest_intent(character_id, quest.quest_id)
        elif quest.status == "ready_to_turn_in":
            result = game_service.turn_in_quest_intent(character_id, quest.quest_id)
        else:
            result = None

        clear_screen()
        lines: list[str] = []
        if result is None:
            lines.append(f"{quest.title} is currently {quest.status}.")
            lines.append("Progress this quest through exploration and return when ready.")
        else:
            lines.extend(list(result.messages or []))
        _render_message_panel("Quest Update", lines, border_style=_BORDER_QUEST, panel_key="quests")
        _prompt_continue()


def _run_explore(game_service, character_id: int):
    clear_screen()
    try:
        explore_view, character, enemies = game_service.explore_intent(character_id)
    except Exception:
        explore_view = None
        character = None
        enemies = []

    if not enemies:
        fallback = "You find nothing of interest today."
        clear_screen()
        _render_message_panel("Explore", [explore_view.message if explore_view else fallback], border_style=_BORDER_LOOP, panel_key="loop")
        _prompt_continue()
        return

    player = character
    scene = _generate_scene()
    clear_screen()
    lines = [
        game_service.encounter_intro_intent(enemies[0]),
        _scene_flavour(scene, verbosity=game_service.get_combat_verbosity()),
        f"Hostiles: {', '.join(f'{enemy.name} ({enemy.hp_current}/{enemy.hp_max})' for enemy in enemies)}",
    ]
    _render_message_panel("Encounter", lines, border_style=_BORDER_LOOP, panel_key="loop")
    _prompt_continue("Press ENTER to start combat...")

    result = game_service.combat_resolve_party_intent(
        player,
        enemies,
        lambda options, p, e, round_no, ctx=None: _choose_combat_action(game_service, options, p, e, round_no, scene),
        choose_target=lambda actor, allies, foes, round_no, scene_ctx, action: _choose_party_target(actor, allies, foes, round_no, scene_ctx, action),
        scene=scene,
    )

    player_after = next((ally for ally in result.allies if int(getattr(ally, "id", 0) or 0) == int(getattr(player, "id", 0) or 0)), None)
    if player_after is not None:
        player = player_after
    game_service.save_character_state(player)

    clear_screen()
    _render_message_panel("Combat Log", [entry.text for entry in result.log], border_style=_BORDER_LOOP, panel_key="loop")

    if result.fled:
        lines = ["You escaped the encounter."]
        retreat = game_service.apply_retreat_consequence_intent(player.id)
        lines.extend(list(retreat.messages or []))
        _render_message_panel("Retreat", lines, border_style=_BORDER_LOOP, panel_key="loop")
        _prompt_continue()
        return

    if result.allies_won:
        lines = ["Your party survives the encounter."]
    else:
        defeat = game_service.apply_defeat_consequence_intent(player.id)
        lines = list(defeat.messages or [])
    _render_message_panel("Encounter Result", lines, border_style=_BORDER_LOOP, panel_key="loop")
    _prompt_continue()


def _combat_lane(actor) -> str:
    flags = getattr(actor, "flags", None)
    if isinstance(flags, dict):
        forced = str(flags.get("combat_lane", "") or "").strip().lower()
        if forced in {"vanguard", "rearguard"}:
            return forced
    class_name = str(getattr(actor, "class_name", "") or "").strip().lower()
    if class_name in {"wizard", "sorcerer", "warlock", "bard"}:
        return "rearguard"
    name = str(getattr(actor, "name", "") or "").strip().lower()
    if any(word in name for word in ("archer", "shaman", "mage", "warlock", "witch", "priest", "acolyte")):
        return "rearguard"
    return "vanguard"


def _choose_party_target(actor, allies, foes, round_no, scene_ctx, action):
    _ = round_no
    _ = scene_ctx
    normalized_action = str(action or "").strip().lower()
    if normalized_action in {"flee", "dash", "dodge", "use item"}:
        return 0

    if normalized_action == "cast spell":
        lane_options = ["Enemy Target", "Ally Target", "Auto"]
        lane_idx = arrow_menu("Cast Spell — Target Group", lane_options)
        if lane_idx == 1:
            target_pool = allies
            side_key = "ally"
        else:
            target_pool = foes
            side_key = "enemy"
    else:
        target_pool = foes
        side_key = "enemy"
    if not target_pool:
        return 0

    _render_party_lane_snapshot(actor=actor, allies=allies, foes=foes)
    options = [f"{row.name} ({row.hp_current}/{row.hp_max}) [{_combat_lane(row).title()}]" for row in target_pool]
    idx = arrow_menu(f"Choose Target — {str(action).title()}", options)
    if idx < 0:
        return 0
    return (side_key, idx)


def _render_party_lane_snapshot(actor, allies, foes):
    clear_screen()
    ally_vanguard = [row for row in allies if _combat_lane(row) == "vanguard"]
    ally_rearguard = [row for row in allies if _combat_lane(row) == "rearguard"]
    enemy_vanguard = [row for row in foes if _combat_lane(row) == "vanguard"]
    enemy_rearguard = [row for row in foes if _combat_lane(row) == "rearguard"]

    lines = [
        f"Acting: {getattr(actor, 'name', 'Unknown')}",
        f"Enemy Vanguard: {', '.join(f'{row.name} ({row.hp_current}/{row.hp_max})' for row in enemy_vanguard) or 'None'}",
        f"Enemy Rearguard: {', '.join(f'{row.name} ({row.hp_current}/{row.hp_max})' for row in enemy_rearguard) or 'None'}",
        "---",
        f"Your Vanguard: {', '.join(f'{row.name} ({row.hp_current}/{row.hp_max})' for row in ally_vanguard) or 'None'}",
        f"Your Rearguard: {', '.join(f'{row.name} ({row.hp_current}/{row.hp_max})' for row in ally_rearguard) or 'None'}",
    ]
    _render_message_panel("Party Formation", lines, border_style=_BORDER_LOOP, panel_key="loop")


def _choose_combat_action(game_service, options, player, enemy, round_no, scene_ctx=None):
    """Render a simple combat decision menu."""
    round_view = game_service.combat_round_view_intent(
        options=options,
        player=player,
        enemy=enemy,
        round_no=round_no,
        scene_ctx=scene_ctx,
    )

    _render_combat_round(round_view)
    idx = arrow_menu(f"Combat — {enemy.name}", round_view.options)
    selected = round_view.options[idx] if 0 <= idx < len(round_view.options) else None
    spell_slug = None
    item_name = None
    if selected == "Cast Spell":
        spell_slug = _choose_spell(game_service, player)
    if selected == "Use Item":
        item_name = _choose_combat_item(game_service, player)
    return game_service.submit_combat_action_intent(
        options=round_view.options,
        selected_index=idx,
        spell_slug=spell_slug,
        item_name=item_name,
    )


def _choose_spell(game_service, player):
    options = game_service.list_spell_options(player)
    if not options:
        clear_screen()
        _render_message_panel("Cast Spell", ["You don't know any spells."], border_style=_BORDER_LOOP, panel_key="loop")
        _prompt_continue()
        return None

    spells_display = [option.label for option in options]
    slugs = [option.slug for option in options]

    choice = arrow_menu("Cast Spell — Combat", spells_display)
    if choice < 0:
        return None
    return slugs[choice]


def _choose_combat_item(game_service, player):
    options = game_service.list_combat_item_options(player)
    if not options:
        clear_screen()
        _render_message_panel("Use Item", ["No usable combat items available."], border_style=_BORDER_LOOP, panel_key="loop")
        _prompt_continue()
        return None

    choice = arrow_menu("Use Item — Combat", options)
    if choice < 0:
        return None
    return options[choice]


def _choose_travel_mode(location_name: str | None = None) -> str | None:
    options = [
        "Road (balanced)",
        "Stealth Path (safer, slower)",
        "Caravan Route (safer, slower)",
        "Back",
    ]
    selected = arrow_menu(f"Travel Mode — {location_name or 'Journey'}", options)
    if selected in {-1, len(options) - 1}:
        return None
    return ("road", "stealth", "caravan")[selected]


def _generate_scene():
    distance = random.choice(["close", "mid", "far"])
    surprise = random.choice(["none", "player", "enemy"])
    terrain = random.choice(["open", "cramped", "difficult"])
    return {"distance": distance, "surprise": surprise, "terrain": terrain}


def _scene_flavour(scene: dict, verbosity: str = "compact") -> str:
    distance = scene.get("distance", "close")
    surprise = scene.get("surprise", "none")
    terrain = scene.get("terrain", "open")
    dist_line = {
        "close": "The enemy is already upon you.",
        "mid": "You spot movement not far away.",
        "far": "You see danger in the distance.",
    }.get(distance, "")
    surprise_line = {
        "player": "You catch them unaware.",
        "enemy": "You're too late - they strike first.",
        "none": "Both sides see each other at the same time.",
    }.get(surprise, "")
    terrain_line = {
        "open": "The ground is clear and open.",
        "cramped": "The space is tight and cluttered.",
        "difficult": "The ground is uneven and treacherous.",
    }.get(terrain, "")
    lines = [line for line in (dist_line, surprise_line, terrain_line) if line]
    limit = 2 if verbosity == "compact" else (3 if verbosity == "normal" else len(lines))
    return "\n".join(lines[:limit])


