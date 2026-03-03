from __future__ import annotations

from dataclasses import dataclass

from rpg.presentation.windowing.contracts import Cell, DisplayController, DisplayMode, InputSource, KeyEvent, RenderTarget

try:
    import pygame
except Exception:  # pragma: no cover - optional dependency fallback
    pygame = None


_KEY_MAP = {
    "up": "UP",
    "down": "DOWN",
    "left": "LEFT",
    "right": "RIGHT",
    "return": "ENTER",
    "escape": "ESC",
    "w": "UP",
    "s": "DOWN",
    "a": "LEFT",
    "d": "RIGHT",
    "q": "ESC",
    "f11": "TOGGLE_FULLSCREEN",
    "backspace": "BACKSPACE",
}


@dataclass
class PygameConfig:
    columns: int = 100
    rows: int = 34
    cell_width: int = 12
    cell_height: int = 20
    caption: str = "Realm of Broken Stars"
    font_path: str | None = None


class PygameWindowHost(RenderTarget, InputSource, DisplayController):
    def __init__(self, config: PygameConfig) -> None:
        if pygame is None:
            raise RuntimeError("pygame is not installed. Install with `pip install pygame`.")
        pygame.init()
        self._config = config
        self._screen = pygame.display.set_mode((config.columns * config.cell_width, config.rows * config.cell_height))
        pygame.display.set_caption(config.caption)
        self._clock = pygame.time.Clock()
        self._mode = DisplayMode.WINDOWED
        self._running = True
        self._font = pygame.font.Font(config.font_path, config.cell_height - 2)

    @property
    def columns(self) -> int:
        return self._config.columns

    @property
    def rows(self) -> int:
        return self._config.rows

    def poll(self) -> list[KeyEvent]:
        events: list[KeyEvent] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                events.append(KeyEvent("QUIT"))
                continue
            if event.type != pygame.KEYDOWN:
                continue
            key_name = pygame.key.name(event.key)
            logical = _KEY_MAP.get(key_name)
            if logical is not None:
                events.append(KeyEvent(logical))
                continue
            text = str(getattr(event, "unicode", "") or "")
            if text and text.isprintable():
                events.append(KeyEvent(f"TEXT:{text}"))
        return events

    def draw(self, frame: list[list[Cell]]) -> None:
        if not self._running:
            return
        cell_w = self._config.cell_width
        cell_h = self._config.cell_height
        for y, row in enumerate(frame[: self.rows]):
            for x, cell in enumerate(row[: self.columns]):
                rect = pygame.Rect(x * cell_w, y * cell_h, cell_w, cell_h)
                self._screen.fill(cell.bg, rect)
                if cell.char == " ":
                    continue
                glyph = self._font.render(cell.char, True, cell.fg)
                self._screen.blit(glyph, (x * cell_w, y * cell_h - 1))
        pygame.display.flip()
        self._clock.tick(30)

    def set_mode(self, mode: DisplayMode) -> None:
        if pygame is None:
            return
        flags = pygame.NOFRAME
        if mode == DisplayMode.FULLSCREEN:
            flags |= pygame.FULLSCREEN
        elif mode == DisplayMode.MAXIMIZED:
            flags |= pygame.RESIZABLE
        self._mode = mode
        self._screen = pygame.display.set_mode(
            (self.columns * self._config.cell_width, self.rows * self._config.cell_height),
            flags,
        )

    def stop(self) -> None:
        self._running = False
        if pygame is not None:
            pygame.quit()

    @property
    def running(self) -> bool:
        return self._running
