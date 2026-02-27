import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.data_tools.build_unified_spells import build_unified_spells_payload


class UnifiedSpellsBuilderTests(unittest.TestCase):
    def test_deduplicates_local_spells_present_in_api(self) -> None:
        api_rows = [
            {"slug": "magic-missile", "name": "Magic Missile", "level_int": 1},
            {"slug": "shield", "name": "Shield", "level_int": 1},
        ]
        local_rows = [
            {"name": "Magic Missile", "level": "1", "school": "Evocation"},
            {"name": "Meteor Burst", "level": "6", "school": "Evocation"},
        ]

        payload = build_unified_spells_payload(local_rows=local_rows, api_rows=api_rows)
        names = [str(item.get("name", "")) for item in payload.get("spells", [])]

        self.assertIn("Magic Missile", names)
        self.assertIn("Shield", names)
        self.assertIn("Meteor Burst", names)
        self.assertEqual(1, names.count("Magic Missile"))
        self.assertEqual(1, int(payload["counts"]["local_duplicates_in_api"]))

    def test_deduplicates_local_duplicates_by_slug(self) -> None:
        payload = build_unified_spells_payload(
            local_rows=[
                {"name": "Starfall", "level": "4"},
                {"name": "Starfall", "level": "4"},
            ],
            api_rows=[],
        )

        spells = payload.get("spells", [])
        self.assertEqual(1, len(spells))
        self.assertEqual("Starfall", spells[0].get("name"))
        self.assertEqual(0, int(payload["counts"]["local_duplicates_in_api"]))


if __name__ == "__main__":
    unittest.main()
