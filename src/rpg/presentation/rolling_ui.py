import asyncio
import random
import sys

from rpg.presentation.menu_controls import clear_screen, prompt_input

try:
    from rich.console import Console
    from rich.panel import Panel
except Exception:  # pragma: no cover - optional dependency fallback
    Console = None
    Panel = None


ATTR_ORDER = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
_CONSOLE = Console() if Console is not None else None


_DIE_PIPS = {
    1: ("     ", "  ●  ", "     "),
    2: ("●    ", "     ", "    ●"),
    3: ("●    ", "  ●  ", "    ●"),
    4: ("●   ●", "     ", "●   ●"),
    5: ("●   ●", "  ●  ", "●   ●"),
    6: ("●   ●", "●   ●", "●   ●"),
}


def _supports_dice_unicode() -> bool:
    encoding = sys.stdout.encoding or "utf-8"
    try:
        "┌─────┐●".encode(encoding)
        return True
    except Exception:
        return False


def _build_die_frame(value: int, *, perspective: str = "right") -> list[str]:
    top, mid, bottom = _DIE_PIPS.get(int(value), _DIE_PIPS[1])
    if not _supports_dice_unicode():
        top = top.replace("●", "o")
        mid = mid.replace("●", "o")
        bottom = bottom.replace("●", "o")
        return [
            "+-----+",
            f"|{top}|",
            f"|{mid}|",
            f"|{bottom}|",
            "+-----+",
        ]
    if perspective == "left":
        return [
            "╱┌─────┐",
            f"││{top}│",
            f"││{mid}│",
            f"││{bottom}│",
            "╲└─────┘",
        ]
    return [
        "┌─────┐╲",
        f"│{top}││",
        f"│{mid}││",
        f"│{bottom}││",
        "└─────┘╱",
    ]


def _render_dice_ascii_faces(values: list[int], offsets: list[int] | None = None, *, frame: int = 0) -> list[str]:
    offsets = list(offsets or [0 for _ in values])
    if not values:
        return ["(no dice)"]

    die_faces = []
    for idx, value in enumerate(values):
        perspective = "right" if ((frame // 3 + idx) % 2 == 0) else "left"
        die_faces.append(_build_die_frame(int(value), perspective=perspective))
    die_width = len(die_faces[0][0])
    normalized_offsets = [max(0, min(2, int(offsets[idx]) if idx < len(offsets) else 0)) for idx in range(len(values))]
    max_offset = max(normalized_offsets, default=0)
    row_count = 5 + max_offset
    spacer = "  "

    rows: list[str] = []
    for row in range(row_count):
        row_chunks: list[str] = []
        for idx, face in enumerate(die_faces):
            source_row = row - normalized_offsets[idx]
            if 0 <= source_row < 5:
                row_chunks.append(face[source_row])
            else:
                row_chunks.append(" " * die_width)
        rows.append(spacer.join(row_chunks).rstrip())

    while rows and not rows[0].strip():
        rows.pop(0)
    while rows and not rows[-1].strip():
        rows.pop()

    return rows


def _rolling_offsets(frame: int, count: int) -> list[int]:
    phase = frame % 10
    offset = 1 if phase in {4, 5} else 0
    return [offset for _ in range(count)]


def render_tumbling_dice_lines(values: list[int], *, frame: int = 0) -> list[str]:
    return _render_dice_ascii_faces(values, offsets=_rolling_offsets(frame, len(values)), frame=frame)


def _prompt_continue(message: str) -> None:
    prompt_input(message)
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


def _render_roll_panel(title: str, lines: list[str], border_style: str = "cyan") -> None:
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
    """Synchronous wrapper that executes the async roll animation flow."""
    asyncio.run(_animate_stat_roll_async(stat_name, final_total, final_rolls, rng=rng))

async def _animate_stat_roll_async(
    stat_name: str,
    final_total: int,
    final_rolls: list[int],
    *,
    rng: random.Random | None = None,
) -> None:
    """Async variant that yields to the event loop during roll animation."""
    frames = 8
    sleep_time = 0.08
    resolved_rng = rng or random.Random()
    fake_rolls = [resolved_rng.randint(1, 6) for _ in range(4)]

    for frame_index in range(frames):
        clear_screen()
        _render_roll_panel(
            f"ROLLING {stat_name} (4d6, drop lowest)",
            [
                "Dice tumbling...",
                *render_tumbling_dice_lines(fake_rolls, frame=frame_index),
                "",
                f"Values: {_render_dice_row(fake_rolls)}",
            ],
        )
        await asyncio.sleep(sleep_time)

    clear_screen()
    lowest = min(final_rolls)
    lowest_idx = final_rolls.index(lowest)

    _render_roll_panel(
        f"{stat_name} RESULT",
        [
            "Final roll lock-in:",
            *_render_dice_ascii_faces(final_rolls, offsets=[0 for _ in final_rolls], frame=0),
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
    detailed = roll_values_with_animation(count=len(ATTR_ORDER), show_intro=True, show_summary=True)
    results: dict[str, int] = {}
    for idx, stat in enumerate(ATTR_ORDER):
        if idx >= len(detailed):
            break
        total, _rolls = detailed[idx]
        results[stat] = int(total)
    for stat in ATTR_ORDER:
        if stat not in results:
            results[stat] = 8
    return results


def roll_values_with_animation(
    count: int = 6,
    *,
    show_intro: bool = False,
    show_summary: bool = False,
) -> list[tuple[int, list[int]]]:
    if show_intro:
        clear_screen()
        _render_roll_panel(
            "ATTRIBUTE ROLLING",
            [
                "You will roll 4d6 for each score, dropping the lowest die.",
                f"Total rolls: {int(max(1, count))}.",
            ],
        )
        _prompt_continue("Press ENTER to begin rolling...")
    else:
        clear_screen()

    session_rng = random.Random()
    total_rolls = max(1, int(count))
    rows: list[tuple[int, list[int]]] = []
    for index in range(total_rolls):
        total, rolls = roll_4d6_drop_lowest(rng=session_rng)
        _animate_stat_roll(f"ROLL {index + 1}", total, rolls, rng=session_rng)
        rows.append((int(total), list(rolls)))

    if show_summary:
        clear_screen()
        summary_lines: list[str] = []
        for idx, (total, rolls) in enumerate(rows, start=1):
            summary_lines.append(f"[{idx}] {int(total)} ({', '.join(str(value) for value in list(rolls))})")
        _render_roll_panel("FINAL ROLLED VALUES", summary_lines)
        _prompt_continue("Press ENTER to assign these rolls...")
    return rows


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
