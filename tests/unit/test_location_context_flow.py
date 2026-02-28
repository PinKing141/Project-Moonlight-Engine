import sys
from pathlib import Path
import unittest

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


class LocationContextFlowTests(unittest.TestCase):
    def _build_service(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=17)
        character = Character(id=901, name="Skye", location_id=1)
        character.money = 30
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Starting Town", biome="village"),
                2: Location(id=2, name="Ashen Wilds", biome="wilderness"),
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
        return service, character_repo, world_repo, character.id

    def test_location_context_defaults_to_town_from_location(self):
        service, _character_repo, _world_repo, character_id = self._build_service()

        context = service.get_location_context_intent(character_id)

        self.assertEqual("town", context.location_type)
        self.assertEqual("Rest at Inn", context.rest_label)
        self.assertEqual("Leave Town", context.travel_label)

    def test_travel_intent_toggles_between_town_and_wilderness(self):
        service, character_repo, _world_repo, character_id = self._build_service()

        first = service.travel_intent(character_id)
        context_after_first = service.get_location_context_intent(character_id)
        updated = character_repo.get(character_id)

        self.assertIn("wilderness", " ".join(first.messages).lower())
        self.assertEqual("wilderness", context_after_first.location_type)
        self.assertEqual(2, updated.location_id)

        second = service.travel_intent(character_id)
        context_after_second = service.get_location_context_intent(character_id)
        updated_again = character_repo.get(character_id)

        self.assertIn("return to town", " ".join(second.messages).lower())
        self.assertEqual("town", context_after_second.location_type)
        self.assertEqual(1, updated_again.location_id)

    def test_travel_destinations_list_excludes_current_location(self):
        service, _character_repo, _world_repo, character_id = self._build_service()

        destinations = service.get_travel_destinations_intent(character_id)

        self.assertEqual(1, len(destinations))
        self.assertEqual(2, destinations[0].location_id)
        self.assertIn("Lv", destinations[0].preview)
        self.assertIn("d", destinations[0].preview)
        self.assertNotIn("Risk", destinations[0].preview)
        self.assertNotIn("Days", destinations[0].preview)
        self.assertGreaterEqual(destinations[0].estimated_days, 1)
        self.assertIn("Modes:", destinations[0].mode_hint)

    def test_travel_intent_accepts_explicit_destination_id(self):
        service, character_repo, _world_repo, character_id = self._build_service()

        result = service.travel_intent(character_id, destination_id=2)
        updated = character_repo.get(character_id)

        self.assertIn("travel to", " ".join(result.messages).lower())
        self.assertEqual(2, updated.location_id)
        self.assertEqual("wilderness", service.get_location_context_intent(character_id).location_type)

    def test_travel_event_is_deterministic_for_same_seed_and_state(self):
        service_a, repo_a, world_repo_a, character_id_a = self._build_service()
        service_b, repo_b, world_repo_b, character_id_b = self._build_service()

        result_a = service_a.travel_intent(character_id_a, destination_id=2)
        result_b = service_b.travel_intent(character_id_b, destination_id=2)

        self.assertEqual(result_a.messages, result_b.messages)
        self.assertEqual(repo_a.get(character_id_a).hp_current, repo_b.get(character_id_b).hp_current)
        self.assertEqual(repo_a.get(character_id_a).money, repo_b.get(character_id_b).money)
        self.assertEqual(
            repo_a.get(character_id_a).flags.get("last_travel_event", {}).get("kind"),
            repo_b.get(character_id_b).flags.get("last_travel_event", {}).get("kind"),
        )

        world_a = world_repo_a.load_default()
        world_b = world_repo_b.load_default()
        rows_a = world_a.flags.get("consequences", []) if isinstance(world_a.flags, dict) else []
        rows_b = world_b.flags.get("consequences", []) if isinstance(world_b.flags, dict) else []
        if rows_a:
            self.assertTrue(
                all(isinstance(row, dict) and str(row.get("kind", "")).startswith("travel_") for row in rows_a)
            )
        self.assertEqual(rows_a, rows_b)

    def test_travel_destination_risk_hint_is_deterministic_for_same_state(self):
        service_a, _repo_a, _world_a, character_id_a = self._build_service()
        service_b, _repo_b, _world_b, character_id_b = self._build_service()

        destinations_a = service_a.get_travel_destinations_intent(character_id_a)
        destinations_b = service_b.get_travel_destinations_intent(character_id_b)

        self.assertEqual([row.preview for row in destinations_a], [row.preview for row in destinations_b])
        self.assertTrue(all("Lv" in row.preview for row in destinations_a))
        self.assertTrue(all("d" in row.preview for row in destinations_a))

    def test_travel_mode_affects_message_and_remains_deterministic(self):
        service_a, _repo_a, _world_a, character_id_a = self._build_service()
        service_b, _repo_b, _world_b, character_id_b = self._build_service()

        result_a = service_a.travel_intent(character_id_a, destination_id=2, travel_mode="stealth")
        result_b = service_b.travel_intent(character_id_b, destination_id=2, travel_mode="stealth")

        self.assertEqual(result_a.messages, result_b.messages)
        self.assertIn("stealth", " ".join(result_a.messages).lower())

    def test_travel_pace_changes_duration(self):
        cautious_service, _cautious_repo, cautious_world_repo, cautious_character_id = self._build_service()
        hurried_service, _hurried_repo, hurried_world_repo, hurried_character_id = self._build_service()

        cautious_before = cautious_world_repo.load_default().current_turn
        hurried_before = hurried_world_repo.load_default().current_turn

        cautious_service.travel_intent(
            cautious_character_id,
            destination_id=2,
            travel_mode="road",
            travel_pace="cautious",
        )
        hurried_service.travel_intent(
            hurried_character_id,
            destination_id=2,
            travel_mode="road",
            travel_pace="hurried",
        )

        cautious_after = cautious_world_repo.load_default().current_turn
        hurried_after = hurried_world_repo.load_default().current_turn
        self.assertGreater(cautious_after - cautious_before, hurried_after - hurried_before)

    def test_hurried_travel_without_rations_builds_exhaustion(self):
        service, character_repo, _world_repo, character_id = self._build_service()

        result = service.travel_intent(
            character_id,
            destination_id=2,
            travel_mode="road",
            travel_pace="hurried",
        )

        updated = character_repo.get(character_id)
        self.assertIsNotNone(updated)
        flags = updated.flags if isinstance(updated.flags, dict) else {}
        survival = flags.get("survival", {}) if isinstance(flags.get("survival", {}), dict) else {}
        self.assertGreater(int(survival.get("travel_exhaustion_level", 0) or 0), 0)
        self.assertIn("exhaustion", " ".join(result.messages).lower())

    def test_travel_phase_advances_world_by_estimated_days(self):
        service, _repo, world_repo, character_id = self._build_service()
        before = world_repo.load_default().current_turn

        destination = service.get_travel_destinations_intent(character_id)[0]
        result = service.travel_intent(character_id, destination_id=destination.location_id, travel_mode="road")
        after = world_repo.load_default().current_turn

        self.assertEqual(before + destination.estimated_days, after)
        self.assertTrue(any(str(message).startswith("Day 1 of") for message in result.messages))

    def test_travel_phase_produces_bounded_event_window_count(self):
        service, _repo, _world_repo, character_id = self._build_service()

        destination = service.get_travel_destinations_intent(character_id)[0]
        result = service.travel_intent(character_id, destination_id=destination.location_id, travel_mode="road")
        event_markers = [
            message
            for message in result.messages
            if isinstance(message, str)
            and (
                "road is clear" in message.lower()
                or "rough detour" in message.lower()
                or "forgotten cache" in message.lower()
                or "roadside skirmish" in message.lower()
                or "quieter paths" in message.lower()
                or "guarded caravan" in message.lower()
            )
        ]

        self.assertLessEqual(len(event_markers), destination.estimated_days)

    def test_travel_prep_purchase_updates_preview_and_consumes_after_trip(self):
        service, _repo, _world_repo, character_id = self._build_service()

        before = service.get_travel_destinations_intent(character_id)[0]
        buy = service.purchase_travel_prep_intent(character_id, "packed_supplies")
        after_purchase = service.get_travel_destinations_intent(character_id)[0]
        travel = service.travel_intent(character_id, destination_id=after_purchase.location_id, travel_mode="road")
        after_trip = service.get_travel_destinations_intent(character_id)[0]

        self.assertIn("Travel prep secured", " ".join(buy.messages))
        self.assertNotIn("Prep", after_purchase.preview)
        self.assertNotEqual(before.estimated_days, after_purchase.estimated_days)
        self.assertIn("Travel prep consumed", " ".join(travel.messages))
        self.assertNotIn("Prep", after_trip.preview)

    def test_travel_prep_preview_remains_deterministic_for_same_seed(self):
        service_a, _repo_a, _world_a, character_id_a = self._build_service()
        service_b, _repo_b, _world_b, character_id_b = self._build_service()

        service_a.purchase_travel_prep_intent(character_id_a, "trail_guards")
        service_b.purchase_travel_prep_intent(character_id_b, "trail_guards")

        previews_a = [row.preview for row in service_a.get_travel_destinations_intent(character_id_a)]
        previews_b = [row.preview for row in service_b.get_travel_destinations_intent(character_id_b)]
        self.assertEqual(previews_a, previews_b)


if __name__ == "__main__":
    unittest.main()
