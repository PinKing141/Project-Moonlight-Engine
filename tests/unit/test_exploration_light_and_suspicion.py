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


class ExplorationLightAndSuspicionTests(unittest.TestCase):
    def _build_service(self, *, dexterity: int = 10, wisdom: int = 10, inventory: list[str] | None = None):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=41)
        world = world_repo.load_default()
        world.current_turn = 1
        world_repo.save(world)

        character = Character(id=951, name="Shade", location_id=1)
        character.attributes["dexterity"] = dexterity
        character.attributes["wisdom"] = wisdom
        character.inventory = list(inventory or [])
        character_repo = InMemoryCharacterRepository({character.id: character})

        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Sunken Crypt", biome="ruins")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )
        return service, character_repo, world_repo, character.id

    def test_scout_mentions_low_light_disadvantage(self) -> None:
        service, _repo, _world_repo, character_id = self._build_service(wisdom=12)

        with mock.patch.object(
            GameService,
            "_world_immersion_state",
            return_value={"weather": "Clear", "time_label": "Day 1, Midnight (01:00)", "phase": "Midnight", "day": 1, "hour": 1},
        ), mock.patch("rpg.application.services.game_service.derive_seed", return_value=1), mock.patch("random.Random.randint", return_value=12):
            result = service.wilderness_action_intent(character_id, "scout")

        self.assertTrue(any("low light" in str(line).lower() for line in result.messages))

    def test_sneak_borderline_sets_suspected_state(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(dexterity=12)

        with mock.patch("rpg.application.services.game_service.derive_seed", return_value=1), mock.patch("random.Random.randint", return_value=12):
            service.wilderness_action_intent(character_id, "sneak")

        saved = character_repo.get(character_id)
        state = dict(saved.flags.get("exploration_state", {}))
        self.assertEqual("suspected", str(state.get("detection_state", "")))
        self.assertNotIn("next_explore_surprise", saved.flags)

    def test_sneak_failure_sets_detected_and_enemy_surprise(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(dexterity=10)

        with mock.patch("rpg.application.services.game_service.derive_seed", return_value=1), mock.patch("random.Random.randint", return_value=1):
            service.wilderness_action_intent(character_id, "sneak")

        saved = character_repo.get(character_id)
        state = dict(saved.flags.get("exploration_state", {}))
        self.assertEqual("detected", str(state.get("detection_state", "")))
        self.assertEqual("enemy", service.consume_next_explore_surprise_intent(character_id))

    def test_wait_and_observe_can_reduce_suspicion(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(wisdom=14)
        character = character_repo.get(character_id)
        character.flags["exploration_state"] = {"detection_state": "suspected", "cause": "noise", "updated_turn": 1}
        character_repo.save(character)

        with mock.patch("rpg.application.services.game_service.derive_seed", return_value=1), mock.patch("random.Random.randint", return_value=20):
            service.wilderness_action_intent(character_id, "wait")

        saved = character_repo.get(character_id)
        state = dict(saved.flags.get("exploration_state", {}))
        self.assertEqual("hidden", str(state.get("detection_state", "")))

    def test_environment_intent_reports_light_and_status(self) -> None:
        service, character_repo, _world_repo, character_id = self._build_service(inventory=["Torch"])
        character = character_repo.get(character_id)
        character.flags["exploration_state"] = {"detection_state": "suspected", "cause": "noise", "updated_turn": 1}
        character_repo.save(character)

        with mock.patch.object(
            GameService,
            "_world_immersion_state",
            return_value={"weather": "Clear", "time_label": "Day 1, Midnight (01:00)", "phase": "Midnight", "day": 1, "hour": 1},
        ):
            env = service.get_exploration_environment_intent(character_id)

        self.assertEqual("Dim", str(env.get("light_level", "")))
        self.assertEqual("Suspected", str(env.get("detection_state", "")))


if __name__ == "__main__":
    unittest.main()
