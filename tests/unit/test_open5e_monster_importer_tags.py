import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.db.mysql.open5e_monster_importer import Open5eMonsterImporter


class _StubRepo:
    def upsert_entities(self, entities, location_id=None):
        raise NotImplementedError

    def get_default_location_id(self):
        return 1


class _StubClient:
    def list_monsters(self, page: int = 1) -> dict:
        return {"results": []}

    def close(self) -> None:
        return None


class Open5eMonsterImporterTagMappingTests(unittest.TestCase):
    def test_map_monster_parses_clean_python_lists(self) -> None:
        importer = Open5eMonsterImporter(repository=_StubRepo(), client=_StubClient())

        entity = importer._map_monster(
            {
                "name": "Ember Ghoul",
                "challenge_rating": "3",
                "type": "undead",
                "subtype": "ghoul",
                "damage_resistances": "fire, poison",
                "actions": [{"name": "Claw", "desc": "+4 to hit, (1d8+2) slashing damage."}],
            }
        )

        self.assertEqual(["undead", "ghoul"], entity.tags)
        self.assertEqual(["fire", "poison"], entity.resistances)
        self.assertIsInstance(entity.tags, list)
        self.assertIsInstance(entity.resistances, list)


if __name__ == "__main__":
    unittest.main()
