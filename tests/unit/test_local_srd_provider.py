import json
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.local_srd_provider import LocalSrdProvider


class LocalSrdProviderTests(unittest.TestCase):
    def test_list_races_reads_local_file_and_paginates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "races.json"
            path.write_text(
                json.dumps(
                    {
                        "results": [
                            {"name": "Aarakocra", "slug": "aarakocra"},
                            {"name": "Genasi", "slug": "genasi"},
                            {"name": "Goliath", "slug": "goliath"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            provider = LocalSrdProvider(root_dir=tmp, page_size=2)
            page1 = provider.list_races(page=1)
            page2 = provider.list_races(page=2)

            self.assertEqual(3, page1["count"])
            self.assertEqual(2, len(page1["results"]))
            self.assertIsNotNone(page1["next"])
            self.assertEqual("Goliath", page2["results"][0]["name"])
            self.assertIsNone(page2["next"])

    def test_get_race_resolves_by_slug_or_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "races.json"
            path.write_text(
                json.dumps(
                    [
                        {"name": "High Elf", "slug": "high-elf", "speed": 30},
                        {"name": "Wood Elf", "speed": 35},
                    ]
                ),
                encoding="utf-8",
            )

            provider = LocalSrdProvider(root_dir=tmp)
            high = provider.get_race("high-elf")
            wood = provider.get_race("wood elf")

            self.assertEqual(30, high["speed"])
            self.assertEqual("Wood Elf", wood["name"])


if __name__ == "__main__":
    unittest.main()
