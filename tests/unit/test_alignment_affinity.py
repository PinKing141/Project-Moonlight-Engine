import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.character import Character, CharacterAlignment
from rpg.domain.models.faction import Faction


class AlignmentAffinityTests(unittest.TestCase):
    def test_character_alignment_defaults_to_true_neutral(self) -> None:
        character = Character(id=1, name="Ayla")
        self.assertEqual(CharacterAlignment.TRUE_NEUTRAL.value, character.alignment)

    def test_character_alignment_normalizes_aliases(self) -> None:
        character = Character(id=2, name="Bran", alignment="lawful good")
        self.assertEqual(CharacterAlignment.LAWFUL_GOOD.value, character.alignment)

    def test_faction_alignment_affinity_uses_direct_key(self) -> None:
        faction = Faction(
            id="wardens",
            name="Wardens",
            alignment_affinities={"lawful_good": 2, "chaotic_evil": -3},
        )
        self.assertEqual(2, faction.alignment_affinity_delta("lawful_good"))
        self.assertEqual(-3, faction.alignment_affinity_delta("chaotic evil"))

    def test_faction_alignment_affinity_falls_back_to_axis_scores(self) -> None:
        faction = Faction(
            id="crown",
            name="The Crown",
            alignment_affinities={"lawful": 2, "good": 1, "chaotic": -2, "evil": -1},
        )
        self.assertEqual(3, faction.alignment_affinity_delta("lawful_good"))
        self.assertEqual(-3, faction.alignment_affinity_delta("chaotic_evil"))


if __name__ == "__main__":
    unittest.main()
