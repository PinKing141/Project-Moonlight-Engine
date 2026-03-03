from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class DisplayMode(str, Enum):
    WINDOWED = "windowed"
    MAXIMIZED = "maximized"
    FULLSCREEN = "fullscreen"


@dataclass(frozen=True)
class Cell:
    char: str = " "
    fg: tuple[int, int, int] = (255, 255, 255)
    bg: tuple[int, int, int] = (0, 0, 0)
    bold: bool = False


@dataclass(frozen=True)
class KeyEvent:
    key: str


class RenderTarget(Protocol):
    """Paints a full frame of fixed-size character cells."""

    @property
    def columns(self) -> int:
        ...

    @property
    def rows(self) -> int:
        ...

    def draw(self, frame: list[list[Cell]]) -> None:
        ...


class InputSource(Protocol):
    """Retrieves logical key events from an input backend."""

    def poll(self) -> list[KeyEvent]:
        ...


class DisplayController(Protocol):
    """Display mode toggles and lifecycle management for a host window."""

    def set_mode(self, mode: DisplayMode) -> None:
        ...

    def stop(self) -> None:
        ...
