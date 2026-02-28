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


class LevelUpUnlockAtomicTests(unittest.TestCase):
    def test_submit_level_up_choice_persists_unlock_operation(self) -> None:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=9)
        character = Character(id=13, name="Rune", level=1, xp=30, location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )

        result = service.submit_level_up_choice_intent(character_id=13, growth_choice="feat")

        self.assertTrue(any("Level up!" in line for line in result.messages))
        rows = character_repo.list_progression_unlocks(13)
        self.assertEqual(1, len(rows))
        self.assertEqual("growth_choice", rows[0]["unlock_kind"])
        self.assertEqual("level_2_feat", rows[0]["unlock_key"])

    def test_skill_training_intents_apply_and_persist(self) -> None:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=11)
        character = Character(
            id=21,
            name="Lark",
            class_name="fighter",
            level=1,
            xp=30,
            location_id=1,
            proficiencies=["Athletics"],
        )
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )

        level_result = service.submit_level_up_choice_intent(character_id=21, growth_choice="vitality")
        self.assertTrue(any("Level up!" in line for line in level_result.messages))

        intent_result = service.declare_skill_training_intent_intent(21, ["athletics"])
        self.assertTrue(any("Training intent" in line for line in intent_result.messages))

        spend_result = service.spend_skill_proficiency_points_intent(21, {"athletics": 1})
        self.assertTrue(any("Athletics proficiency is now +2" in line for line in spend_result.messages))

        status = service.get_skill_training_status_intent(21)
        modifiers = status.get("modifiers", {}) if isinstance(status.get("modifiers", {}), dict) else {}
        self.assertEqual(2, int(modifiers.get("athletics", 0) or 0))

    def test_subclass_unlocks_are_persisted_as_progression_records(self) -> None:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=17)
        character = Character(
            id=31,
            name="Kora",
            class_name="fighter",
            level=2,
            xp=50,
            location_id=1,
            flags={"subclass_slug": "paragon", "subclass_name": "The Paragon"},
        )
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )

        result = service.submit_level_up_choice_intent(character_id=31, growth_choice="feat")

        self.assertTrue(any("Subclass advancement unlocked" in line for line in result.messages))
        rows = character_repo.list_progression_unlocks(31)
        keys = {str(row.get("unlock_key", "")) for row in rows}
        self.assertIn("subclass_paragon_tier_1", keys)


if __name__ == "__main__":
    unittest.main()
