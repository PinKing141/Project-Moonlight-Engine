import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.mechanical_flavour_enricher import MechanicalFlavourEnricher


class _FakeLexicalClient:
    def __init__(self, words=None):
        self._words = list(words or [])

    def related_adjectives(self, noun: str, max_words: int = 8) -> list[str]:
        _ = noun, max_words
        return list(self._words)


class MechanicalFlavourEnricherTests(unittest.TestCase):
    def test_combat_line_is_deterministic_for_same_context(self) -> None:
        enricher = MechanicalFlavourEnricher(
            lexical_client=_FakeLexicalClient(words=["grim", "volatile", "urgent"]),
            enabled=True,
            max_words=8,
        )

        first = enricher.build_combat_line(
            actor="player",
            action="attack",
            enemy_kind="undead",
            terrain="open",
            round_no=2,
        )
        second = enricher.build_combat_line(
            actor="player",
            action="attack",
            enemy_kind="undead",
            terrain="open",
            round_no=2,
        )

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("The exchange turns "))

    def test_environment_line_changes_with_context(self) -> None:
        enricher = MechanicalFlavourEnricher(
            lexical_client=_FakeLexicalClient(words=["bitter", "blinding", "restless"]),
            enabled=True,
            max_words=8,
        )

        cold = enricher.build_environment_line(
            event_kind="hazard_failed",
            biome="tundra",
            hazard_name="Whiteout Winds",
            world_turn=4,
        )
        heat = enricher.build_environment_line(
            event_kind="hazard_failed",
            biome="desert",
            hazard_name="Sandstorm",
            world_turn=4,
        )

        self.assertNotEqual(cold, heat)
        self.assertIn("feels", cold)
        self.assertIn("feels", heat)


if __name__ == "__main__":
    unittest.main()
