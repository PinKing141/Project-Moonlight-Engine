from __future__ import annotations

from rpg.presentation.windowing.contracts import Cell
from rpg.presentation.windowing.frame_buffer import FrameBuffer

try:
    from rich.console import Console
except Exception:  # pragma: no cover - optional dependency fallback
    Console = None


class RichOffscreenRenderer:
    """Renders Rich markup into a fixed cell grid with foreground/background colors."""

    def __init__(self, *, columns: int, rows: int) -> None:
        self.columns = max(20, int(columns))
        self.rows = max(10, int(rows))
        if Console is None:
            raise RuntimeError("Rich is required for offscreen rendering.")
        self._console = Console(
            width=self.columns,
            height=self.rows,
            record=False,
            force_terminal=True,
            color_system="truecolor",
            legacy_windows=False,
            soft_wrap=False,
            highlight=False,
            file=None,
        )

    def render_markup(self, markup: str) -> list[list[Cell]]:
        buffer = FrameBuffer(columns=self.columns, rows=self.rows)
        renderable = self._console.render_str(markup)
        lines = self._console.render_lines(renderable, pad=True, new_lines=False)
        for y, line in enumerate(lines[: self.rows]):
            x = 0
            for segment in line:
                text = segment.text or ""
                style = segment.style
                fg = (255, 255, 255)
                bg = (0, 0, 0)
                bold = False
                if style is not None:
                    bold = bool(getattr(style, "bold", False))
                    if style.color is not None:
                        true = style.color.get_truecolor()
                        fg = (true.red, true.green, true.blue)
                    if style.bgcolor is not None:
                        true_bg = style.bgcolor.get_truecolor()
                        bg = (true_bg.red, true_bg.green, true_bg.blue)
                for char in text:
                    if x >= self.columns:
                        break
                    buffer.put(x, y, Cell(char=char, fg=fg, bg=bg, bold=bold))
                    x += 1
                if x >= self.columns:
                    break
        return buffer.rows_view()
