from __future__ import annotations


class Phase25LoopSelector:
    """Deterministic menu selector used by Phase25 scripted capture/tests."""

    def __init__(self) -> None:
        self._root_sequence = [0, 1, 0, 2, 4]
        self.state = {
            "root_actions": 0,
            "quest_board_visits": 0,
            "quest_accepts": 0,
            "wilderness_actions": 0,
            "travel_actions": 0,
            "travel_hops": 0,
        }

    def choose(self, title, options) -> int:
        text = str(title or "")
        rows = list(options or [])

        if text.endswith("— Actions"):
            idx = (
                self._root_sequence[self.state["root_actions"]]
                if self.state["root_actions"] < len(self._root_sequence)
                else 4
            )
            self.state["root_actions"] += 1
            if idx == 1:
                self.state["travel_actions"] += 1
            return idx

        if text.startswith("Town Options"):
            if self.state["quest_board_visits"] == 0:
                return 1
            return 8

        if text.startswith("Quest Board"):
            self.state["quest_board_visits"] += 1
            if self.state["quest_accepts"] == 0 and len(rows) > 1:
                self.state["quest_accepts"] += 1
                return 0
            return len(rows) - 1

        if text.startswith("Travel Mode"):
            return 0

        if text.startswith("Travel Pace"):
            return 1

        if "Wilderness Actions" in text:
            self.state["wilderness_actions"] += 1
            return 5

        if text.startswith("Wilderness Rest"):
            return 1

        if text in {"Leave Town", "Return to Town"}:
            if len(rows) > 1:
                self.state["travel_hops"] += 1
                return 0
            return len(rows) - 1 if rows else -1

        return len(rows) - 1 if rows else -1

