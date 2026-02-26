import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.encounter_definition import EncounterDefinition, EncounterSlot
from rpg.domain.models.entity import Entity
from rpg.domain.models.faction import Faction
from rpg.domain.models.stats import CombatStats
from rpg.domain.repositories import EntityRepository
from rpg.domain.services.encounter_planner import EncounterPlanner


class _StubEntityRepository(EntityRepository):
    def __init__(self, entities: list[Entity]):
        self._by_id = {entity.id: entity for entity in entities}

    def get(self, entity_id: int):
        return self._by_id.get(entity_id)

    def get_many(self, entity_ids: list[int]):
        return [self._by_id[eid] for eid in entity_ids if eid in self._by_id]

    def list_for_level(self, target_level: int, tolerance: int = 2):
        return [
            entity
            for entity in self._by_id.values()
            if target_level - tolerance <= entity.level <= target_level + tolerance
        ]

    def list_by_location(self, location_id: int):
        return list(self._by_id.values())


class CombatStatsTests(unittest.TestCase):
    def test_threat_rating_accounts_for_defense_and_damage(self):
        stats = CombatStats(
            hp=18,
            attack_min=2,
            attack_max=5,
            armor=3,
            armour_class=13,
            attack_bonus=2,
        )

        base_rating = stats.threat_rating
        amplified = stats.with_bonus(hp_bonus=4, damage_bonus=1).threat_rating

        self.assertGreater(base_rating, 10)
        self.assertGreater(amplified, base_rating)


class EncounterPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entities = [
            Entity(id=1, name="Goblin", level=1, hp=8),
            Entity(id=2, name="Wolf", level=2, hp=10),
        ]
        self.repo = _StubEntityRepository(self.entities)
        self.planner = EncounterPlanner(self.repo)

    def test_filters_by_location_and_level(self):
        defs = [
            EncounterDefinition(
                id="goblin_scouts",
                name="Goblin Scouts",
                level_min=1,
                level_max=2,
                location_ids=[1],
                slots=[EncounterSlot(entity_id=1, min_count=1, max_count=2)],
            ),
            EncounterDefinition(
                id="wolf_hunters",
                name="Wolf Hunters",
                level_min=4,
                level_max=8,
                location_ids=[2],
                slots=[EncounterSlot(entity_id=2, min_count=2, max_count=3)],
            ),
        ]

        chosen, enemies = self.planner.plan_encounter(
            definitions=defs,
            player_level=1,
            location_id=1,
            seed=99,
            max_enemies=3,
        )

        self.assertIsNotNone(chosen)
        self.assertEqual("goblin_scouts", chosen.id)
        self.assertTrue(all(enemy.id == 1 for enemy in enemies))

    def test_respects_max_enemies(self):
        defs = [
            EncounterDefinition(
                id="goblin_band",
                name="Goblin Band",
                level_min=1,
                level_max=3,
                location_ids=[1],
                slots=[EncounterSlot(entity_id=1, min_count=1, max_count=4)],
            ),
        ]

        chosen, enemies = self.planner.plan_encounter(
            definitions=defs,
            player_level=2,
            location_id=1,
            seed=1,
            max_enemies=2,
        )

        self.assertLessEqual(len(enemies), 2)
        self.assertEqual("goblin_band", chosen.id)


class FactionModelTests(unittest.TestCase):
    def test_attitude_changes_with_reputation(self):
        faction = Faction(id="wardens", name="Emerald Wardens")
        self.assertEqual("neutral", faction.attitude_towards("hero"))

        faction.adjust_reputation("hero", 10)
        self.assertEqual("friendly", faction.attitude_towards("hero"))

        faction.adjust_reputation("hero", -35)
        self.assertEqual("hostile", faction.attitude_towards("hero"))


if __name__ == "__main__":
    unittest.main()
