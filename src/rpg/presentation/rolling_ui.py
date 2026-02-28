import asyncio
import random
import time

from rpg.presentation.menu_controls import clear_screen

try:
    from rich.console import Console
    from rich.panel import Panel
except Exception:  # pragma: no cover - optional dependency fallback
    Console = None
    Panel = None


ATTR_ORDER = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
_CONSOLE = Console() if Console is not None else None


def _prompt_continue(message: str) -> None:
    if _CONSOLE is not None:
        _CONSOLE.input(f"[dim]{message}[/dim]")
        clear_screen()
        return
    input(message)
    clear_screen()


def roll_4d6_drop_lowest(rng: random.Random | None = None) -> tuple[int, list[int]]:
    """Roll 4d6, drop the lowest, return (total, rolls)."""
    resolved_rng = rng or random.Random()
    rolls = [resolved_rng.randint(1, 6) for _ in range(4)]
    total = sum(rolls) - min(rolls)
    return total, rolls


def _render_dice_row(rolls: list[int], highlight_index: int | None = None) -> str:
    """Render dice like: [4] [2] [6] [3]; parentheses mark dropped die."""
    parts = []
    for i, r in enumerate(rolls):
        face = f"[{r}]"
        if highlight_index is not None and i == highlight_index:
            face = f"({r})"
        parts.append(face)
    return "  ".join(parts)


def _render_roll_panel(title: str, lines: list[str], border_style: str = "yellow") -> None:
    body = "\n".join(lines)
    if _CONSOLE is not None and Panel is not None:
        _CONSOLE.print(
            Panel.fit(
                body,
                title=f"[bold yellow]{title}[/bold yellow]",
                border_style=border_style,
            )
        )
        return

    print("=" * 40)
    print(f" {title} ".center(40))
    print("=" * 40)
    for line in lines:
        print(line)


def _animate_stat_roll(stat_name: str, final_total: int, final_rolls: list[int], *, rng: random.Random | None = None) -> None:
    """Show a quick rolling animation then reveal the final result."""
    frames = 12
    sleep_time = 0.05
    resolved_rng = rng or random.Random()

    for _ in range(frames):
        clear_screen()
        fake_rolls = [resolved_rng.randint(1, 6) for _ in range(4)]
        _render_roll_panel(
            f"ROLLING {stat_name} (4d6, drop lowest)",
            [
                f"Dice: {_render_dice_row(fake_rolls)}",
                "",
                "Rolling...",
            ],
        )
        time.sleep(sleep_time)

    # Final reveal
    clear_screen()

async def _animate_stat_roll_async(
    stat_name: str,
    final_total: int,
    final_rolls: list[int],
    *,
    rng: random.Random | None = None,
) -> None:
    """Async variant that yields to the event loop during roll animation."""
    frames = 12
    sleep_time = 0.05
    resolved_rng = rng or random.Random()

    for _ in range(frames):
        clear_screen()
        fake_rolls = [resolved_rng.randint(1, 6) for _ in range(4)]
        _render_roll_panel(
            f"ROLLING {stat_name} (4d6, drop lowest)",
            [
                f"Dice: {_render_dice_row(fake_rolls)}",
                "",
                "Rolling...",
            ],
        )
        await asyncio.sleep(sleep_time)

    clear_screen()
    lowest = min(final_rolls)
    lowest_idx = final_rolls.index(lowest)

    _render_roll_panel(
        f"{stat_name} RESULT",
        [
            f"Final dice: {_render_dice_row(final_rolls, highlight_index=lowest_idx)}",
            f"(Lowest die ({lowest}) is dropped.)",
            "",
            f"{stat_name} = {final_total}",
        ],
    )
    _prompt_continue("Press ENTER to continue...")


    lowest = min(final_rolls)
    lowest_idx = final_rolls.index(lowest)

    _render_roll_panel(
        f"{stat_name} RESULT",
        [
            f"Final dice: {_render_dice_row(final_rolls, highlight_index=lowest_idx)}",
            f"(Lowest die ({lowest}) is dropped.)",
            "",
            f"{stat_name} = {final_total}",
        ],
    )
    _prompt_continue("Press ENTER to continue...")


def roll_attributes_with_animation() -> dict[str, int]:
    """
    Full rolling UI:
      - For each attribute in ATTR_ORDER, show animation
      - Roll 4d6 drop lowest
      - Return a dict like {'STR': 16, 'DEX': 12, ...}
    """
    clear_screen()
    _render_roll_panel(
        "ATTRIBUTE ROLLING",
        [
            "You will roll 4d6 for each attribute, dropping the lowest die.",
            "Order: STR, DEX, CON, INT, WIS, CHA.",
        ],
    )
    _prompt_continue("Press ENTER to begin rolling...")

    results: dict[str, int] = {}
    session_rng = random.Random()

    for stat in ATTR_ORDER:
        total, rolls = roll_4d6_drop_lowest(rng=session_rng)
        _animate_stat_roll(stat, total, rolls, rng=session_rng)
        results[stat] = total

    # Summary screen
    clear_screen()
    _render_roll_panel(
        "FINAL ATTRIBUTE ROLLS",
        [f"{stat}: {results[stat]}" for stat in ATTR_ORDER],
    )
    _prompt_continue("Press ENTER to accept these rolls...")

    return results


async def roll_attributes_with_animation_async() -> dict[str, int]:
    """Async roll flow that avoids blocking the event loop during animation."""
    clear_screen()
    _render_roll_panel(
        "ATTRIBUTE ROLLING",
        [
            "You will roll 4d6 for each attribute, dropping the lowest die.",
            "Order: STR, DEX, CON, INT, WIS, CHA.",
        ],
    )
    _prompt_continue("Press ENTER to begin rolling...")

    results: dict[str, int] = {}
    session_rng = random.Random()

    for stat in ATTR_ORDER:
        total, rolls = roll_4d6_drop_lowest(rng=session_rng)
        await _animate_stat_roll_async(stat, total, rolls, rng=session_rng)
        results[stat] = total

    clear_screen()
    _render_roll_panel(
        "FINAL ATTRIBUTE ROLLS",
        [f"{stat}: {results[stat]}" for stat in ATTR_ORDER],
    )
    _prompt_continue("Press ENTER to accept these rolls...")

    return results
