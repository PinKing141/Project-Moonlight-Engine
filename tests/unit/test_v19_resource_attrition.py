import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class V19ResourceAttritionTests(unittest.TestCase):
    def _build_service(self, *, inventory: list[str] | None = None, location_id: int = 1):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=29)
        character = Character(9901, "Vera")
        character.location_id = location_id
        character.hp_current = 16
        character.hp_max = 24
        character.money = 20
        character.inventory = list(inventory or [])
        character.flags = {"survival": {"travel_exhaustion_level": 2}}
        character_id = int(character.id or 0)
        character_repo = InMemoryCharacterRepository({character_id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Marsh Camp", biome="wilderness"),
                2: Location(id=2, name="Town", biome="village"),
            }
        )
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )
        return service, character_repo, world_repo, character_id

    def test_environment_intent_surfaces_resource_pressure(self) -> None:
        service, _character_repo, _world_repo, character_id = self._build_service(
            inventory=["Sturdy Rations", "Torch", "Arrows x20"]
        )

        env = service.get_exploration_environment_intent(character_id)

        self.assertIn("resource_pressure", env)
        self.assertIn("resource_note", env)
        self.assertIn("Resources:", str(env.get("resource_pressure", "")))
        self.assertTrue(str(env.get("resource_note", "")).strip())

    def test_town_view_pressure_includes_resource_pressure(self) -> None:
        service, _character_repo, _world_repo, character_id = self._build_service(
            inventory=["Chain Mail", "Shield", "Longbow", "Torch"],
            location_id=2,
        )

        town = service.get_town_view_intent(character_id)

        self.assertIn("Resources:", str(getattr(town, "pressure_summary", "")))
        self.assertTrue(any("Encumbrance:" in str(line) for line in list(getattr(town, "pressure_lines", []) or [])))

    def test_travel_route_note_warns_when_resources_are_low(self) -> None:
        service, _character_repo, _world_repo, character_id = self._build_service(inventory=[])

        destinations = service.get_travel_destinations_intent(character_id)

        self.assertTrue(destinations)
        self.assertTrue(any("resource pressure" in str(row.route_note).lower() for row in destinations))

    def test_short_rest_interruption_still_reports_interruption_and_keeps_fatigue_controlled(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(
            inventory=["Sturdy Rations"],
            location_id=1,
        )

        with mock.patch("random.Random.randint", return_value=1):
            result = service.short_rest_intent(character_id)

        saved = character_repo.get(character_id)
        self.assertIsNotNone(saved)
        assert saved is not None
        survival = dict((saved.flags or {}).get("survival", {}))
        self.assertLessEqual(int(survival.get("travel_exhaustion_level", 0) or 0), 2)
        self.assertTrue(any("rest interrupted" in str(line).lower() for line in result.messages))

    def test_overburdened_travel_sets_band_and_adds_exhaustion_pressure(self) -> None:
        inventory = [
            "Chain Mail",
            "Shield",
            "Longbow",
            "Warhammer",
            "Rope",
            "Lantern",
            "Torch",
            "Torch",
            "Sturdy Rations",
            "Sturdy Rations",
            "Climbing Kit",
        ]
        service, character_repo, _world_repo, character_id = self._build_service(inventory=inventory)

        result = service.travel_intent(character_id, destination_id=2, travel_mode="road", travel_pace="hurried")

        saved = character_repo.get(character_id)
        self.assertIsNotNone(saved)
        assert saved is not None
        survival = dict((saved.flags or {}).get("survival", {}))
        self.assertEqual("Overburdened", str(survival.get("encumbrance_band", "")))
        self.assertGreaterEqual(int(survival.get("travel_exhaustion_level", 0) or 0), 2)
        self.assertTrue(any("resources:" in str(line).lower() for line in result.messages))

    def test_rest_warning_intent_surfaces_interruption_risk(self) -> None:
        service, _character_repo, _world_repo, character_id = self._build_service(inventory=[])

        warnings = service.get_resource_risk_warnings_intent(
            character_id,
            action="rest",
            rest_kind="long_rest",
        )

        self.assertTrue(warnings)
        self.assertTrue(any("rest risk" in str(line).lower() for line in warnings))
        self.assertTrue(any("likely interruption impact" in str(line).lower() for line in warnings))

    def test_short_rest_major_interruption_can_worsen_exhaustion(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(
            inventory=["Sturdy Rations"],
            location_id=1,
        )
        with mock.patch.object(service, "_rest_interruption_roll", return_value=(True, "violent weather", "major")):
            result = service.short_rest_intent(character_id)

        saved = character_repo.get(character_id)
        self.assertIsNotNone(saved)
        assert saved is not None
        survival = dict((saved.flags or {}).get("survival", {}))
        self.assertEqual(4, int(survival.get("travel_exhaustion_level", 0) or 0))
        self.assertTrue(any("major severity" in str(line).lower() for line in result.messages))
        self.assertTrue(any("exhaustion worsens" in str(line).lower() for line in result.messages))

    def test_long_rest_major_interruption_limits_recovery_and_worsens_exhaustion(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(
            inventory=["Sturdy Rations"],
            location_id=1,
        )
        before = character_repo.get(character_id)
        self.assertIsNotNone(before)
        assert before is not None
        hp_before = int(before.hp_current)
        with mock.patch.object(service, "_rest_interruption_roll", return_value=(True, "hostile movement nearby", "major")):
            result = service.long_rest_intent(character_id)

        saved = character_repo.get(character_id)
        self.assertIsNotNone(saved)
        assert saved is not None
        survival = dict((saved.flags or {}).get("survival", {}))
        self.assertEqual(3, int(survival.get("travel_exhaustion_level", 0) or 0))
        self.assertGreater(int(saved.hp_current), hp_before)
        self.assertLess(int(saved.hp_current), int(saved.hp_max))
        self.assertTrue(any("major severity" in str(line).lower() for line in result.messages))
        self.assertTrue(any("exhaustion worsens" in str(line).lower() for line in result.messages))

    def test_short_rest_hostile_movement_reduces_slot_recovery_and_adds_flavor(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(
            inventory=["Sturdy Rations"],
            location_id=1,
        )
        character = character_repo.get(character_id)
        self.assertIsNotNone(character)
        assert character is not None
        character.spell_slots_max = 3
        character.spell_slots_current = 0
        character_repo.save(character)

        with mock.patch.object(service, "_rest_interruption_roll", return_value=(True, "hostile movement nearby", "moderate")):
            result = service.short_rest_intent(character_id)

        saved = character_repo.get(character_id)
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(0, int(saved.spell_slots_current))
        self.assertTrue(any("little time for focus" in str(line).lower() for line in result.messages))

    def test_long_rest_supply_shortage_interruption_increases_fatigue(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(
            inventory=[],
            location_id=1,
        )

        with mock.patch.object(service, "_rest_interruption_roll", return_value=(True, "supply shortages", "moderate")):
            result = service.long_rest_intent(character_id)

        saved = character_repo.get(character_id)
        self.assertIsNotNone(saved)
        assert saved is not None
        survival = dict((saved.flags or {}).get("survival", {}))
        self.assertEqual(3, int(survival.get("travel_exhaustion_level", 0) or 0))
        self.assertTrue(any("without enough supplies" in str(line).lower() for line in result.messages))
        self.assertTrue(any("exhaustion worsens" in str(line).lower() for line in result.messages))

    def test_travel_warning_intent_surfaces_resource_pressure(self) -> None:
        service, _character_repo, _world_repo, character_id = self._build_service(inventory=[])

        warnings = service.get_resource_risk_warnings_intent(character_id, action="travel", destination_id=2)

        self.assertTrue(warnings)
        self.assertTrue(any("resource pressure" in str(line).lower() for line in warnings))

    def test_recovery_status_includes_load_and_fatigue_labels(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(
            inventory=["Chain Mail", "Shield", "Longbow", "Climbing Kit"],
            location_id=1,
        )
        character = character_repo.get(character_id)
        self.assertIsNotNone(character)
        assert character is not None
        flags = dict(character.flags or {})
        flags["recovery_state"] = {
            "active": True,
            "turn": 1,
            "hp_restored": int(character.hp_current),
            "gold_lost": 3,
            "location": "Marsh Camp",
        }
        character.flags = flags
        character_repo.save(character)

        note = service.get_recovery_status_intent(character_id)

        self.assertTrue(note)
        self.assertIn("travel fatigue", str(note).lower())
        self.assertIn("load", str(note).lower())


if __name__ == "__main__":
    unittest.main()
