import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.encounter_service import EncounterService
from rpg.domain.models.entity import Entity
from rpg.domain.repositories import EntityRepository


class _StubEntityRepository(EntityRepository):
    def __init__(self) -> None:
        self._entities = [
            Entity(id=1, name="Wisp", level=2, hp=8, hp_current=8, hp_max=8),
            Entity(id=2, name="Marauder", level=2, hp=10, hp_current=10, hp_max=10),
        ]

    def get(self, entity_id: int):
        for row in self._entities:
            if row.id == entity_id:
                return row
        return None

    def get_many(self, entity_ids: list[int]):
        return [row for row in self._entities if row.id in entity_ids]

    def list_for_level(self, target_level: int, tolerance: int = 2):
        lower = target_level - tolerance
        upper = target_level + tolerance
        return [row for row in self._entities if lower <= row.level <= upper]

    def list_by_location(self, location_id: int):
        return list(self._entities)

    def list_by_level_band(self, level_min: int, level_max: int):
        return [row for row in self._entities if level_min <= row.level <= level_max]


class _HighVarianceLocationEntityRepository(EntityRepository):
    def __init__(self) -> None:
        self._entities = [
            Entity(id=1, name="Rat", level=1, hp=6, hp_current=6, hp_max=6),
            Entity(id=2, name="Ancient Horror", level=20, hp=180, hp_current=180, hp_max=180),
        ]

    def get(self, entity_id: int):
        for row in self._entities:
            if row.id == entity_id:
                return row
        return None

    def get_many(self, entity_ids: list[int]):
        return [row for row in self._entities if row.id in entity_ids]

    def list_for_level(self, target_level: int, tolerance: int = 2):
        lower = target_level - tolerance
        upper = target_level + tolerance
        return [row for row in self._entities if lower <= row.level <= upper]

    def list_by_location(self, location_id: int):
        return list(self._entities)

    def list_by_level_band(self, level_min: int, level_max: int):
        return [row for row in self._entities if level_min <= row.level <= level_max]


class EncounterServiceHazardTests(unittest.TestCase):
    def test_generate_plan_includes_deterministic_hazards(self) -> None:
        service = EncounterService(entity_repo=_StubEntityRepository())

        first = service.generate_plan(
            location_id=1,
            player_level=3,
            world_turn=4,
            faction_bias=None,
            max_enemies=2,
            location_biome="swamp",
        )
        second = service.generate_plan(
            location_id=1,
            player_level=3,
            world_turn=4,
            faction_bias=None,
            max_enemies=2,
            location_biome="swamp",
        )

        self.assertEqual(first.hazards, second.hazards)
        self.assertTrue(first.hazards)
        self.assertTrue(all(isinstance(hazard, str) and hazard for hazard in first.hazards))

    def test_generate_plan_respects_world_flag_peaceful_override(self) -> None:
        service = EncounterService(entity_repo=_StubEntityRepository())

        plan = service.generate_plan(
            location_id=1,
            player_level=3,
            world_turn=8,
            faction_bias=None,
            max_enemies=2,
            location_biome="forest",
            world_flags={"location:1:peaceful": True},
        )

        self.assertEqual([], plan.enemies)
        self.assertEqual([], plan.hazards)
        self.assertEqual("peaceful", plan.source)

    def test_world_flags_participate_in_seed_context(self) -> None:
        service = EncounterService(entity_repo=_StubEntityRepository())

        signature_a: list[tuple[tuple[str, ...], tuple[int, ...]]] = []
        signature_b: list[tuple[tuple[str, ...], tuple[int, ...]]] = []
        for world_turn in range(10, 16):
            plan_a = service.generate_plan(
                location_id=1,
                player_level=3,
                world_turn=world_turn,
                faction_bias=None,
                max_enemies=2,
                location_biome="forest",
                world_flags={"quest:first_hunt:turned_in": "false"},
            )
            plan_b = service.generate_plan(
                location_id=1,
                player_level=3,
                world_turn=world_turn,
                faction_bias=None,
                max_enemies=2,
                location_biome="forest",
                world_flags={"quest:first_hunt:turned_in": "true"},
            )
            signature_a.append((tuple(plan_a.hazards), tuple(enemy.id for enemy in plan_a.enemies)))
            signature_b.append((tuple(plan_b.hazards), tuple(enemy.id for enemy in plan_b.enemies)))

        self.assertNotEqual(signature_a, signature_b)

    def test_location_pool_filters_out_extreme_enemy_levels(self) -> None:
        service = EncounterService(entity_repo=_HighVarianceLocationEntityRepository())

        plan = service.generate_plan(
            location_id=1,
            player_level=1,
            world_turn=1,
            faction_bias=None,
            max_enemies=2,
            location_biome="wilderness",
        )

        self.assertTrue(plan.enemies)
        self.assertTrue(all(enemy.level <= 3 for enemy in plan.enemies))
        self.assertTrue(all(enemy.level >= 1 for enemy in plan.enemies))


if __name__ == "__main__":
    unittest.main()
