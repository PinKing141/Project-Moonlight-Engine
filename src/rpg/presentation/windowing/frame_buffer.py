from __future__ import annotations

from dataclasses import dataclass

from rpg.presentation.windowing.contracts import Cell


@dataclass
class FrameBuffer:
    columns: int
    rows: int

    def __post_init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        self.grid: list[list[Cell]] = [[Cell() for _ in range(self.columns)] for _ in range(self.rows)]

    def put(self, x: int, y: int, cell: Cell) -> None:
        if y < 0 or y >= self.rows or x < 0 or x >= self.columns:
            return
        self.grid[y][x] = cell

    def rows_view(self) -> list[list[Cell]]:
        return self.grid
