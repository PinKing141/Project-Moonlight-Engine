import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.quest_service import QuestService
from rpg.domain.events import MonsterSlain, TickAdvanced
from rpg.domain.models.character import Character
from rpg.domain.models.world import World
from rpg.domain.repositories import CharacterRepository, WorldRepository


class _StubWorldRepository(WorldRepository):
    def __init__(self) -> None:
        self.world = World(id=1, name="Test", current_turn=0, flags={})

    def load_default(self):
        return self.world

    def save(self, world: World) -> None:
        self.world = world


class _StubCharacterRepository(CharacterRepository):
    def __init__(self, characters: dict[int, Character]) -> None:
        self.characters = characters

    def get(self, character_id: int):
        return self.characters.get(character_id)

    def list_all(self):
        return list(self.characters.values())

    def save(self, character: Character) -> None:
        self.characters[character.id] = character

    def find_by_location(self, location_id: int):
        return [c for c in self.characters.values() if c.location_id == location_id]

    def create(self, character: Character, location_id: int):
        character.location_id = location_id
        self.characters[character.id] = character
        return character


class QuestServiceTests(unittest.TestCase):
    def test_tick_posts_multiple_quest_contracts(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1, xp=0, money=0)
        char_repo = _StubCharacterRepository({hero.id: hero})

        service = QuestService(world_repo=world_repo, character_repo=char_repo, event_bus=bus)
        service.register_handlers()

        bus.publish(TickAdvanced(turn_after=1))

        quests = world_repo.world.flags.get("quests", {})
        self.assertIn("first_hunt", quests)
        self.assertIn("trail_patrol", quests)
        self.assertIn("supply_drop", quests)
        self.assertEqual("available", quests["first_hunt"]["status"])
        self.assertEqual("kill_any", quests["trail_patrol"]["objective_kind"])
        self.assertEqual("travel_count", quests["supply_drop"]["objective_kind"])

    def test_tick_then_monster_slain_marks_quest_ready_to_turn_in(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1, xp=0, money=0)
        char_repo = _StubCharacterRepository({hero.id: hero})

        service = QuestService(world_repo=world_repo, character_repo=char_repo, event_bus=bus)
        service.register_handlers()

        bus.publish(TickAdvanced(turn_after=1))
        quest = world_repo.world.flags.get("quests", {}).get("first_hunt")
        self.assertIsNotNone(quest)
        self.assertEqual("available", quest["status"])

        # emulate acceptance through app intent layer
        quest["status"] = "active"

        bus.publish(MonsterSlain(monster_id=99, location_id=1, by_character_id=11, turn=1))

        quest = world_repo.world.flags.get("quests", {}).get("first_hunt")
        self.assertEqual("ready_to_turn_in", quest["status"])
        self.assertEqual(1, quest["progress"])
        self.assertEqual(11, quest["owner_character_id"])
        updated = char_repo.get(11)
        self.assertEqual(0, updated.xp)
        self.assertEqual(0, updated.money)

    def test_active_travel_contract_progresses_on_ticks(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1, xp=0, money=0)
        char_repo = _StubCharacterRepository({hero.id: hero})

        service = QuestService(world_repo=world_repo, character_repo=char_repo, event_bus=bus)
        service.register_handlers()

        bus.publish(TickAdvanced(turn_after=1))
        quest = world_repo.world.flags.get("quests", {}).get("supply_drop")
        self.assertIsNotNone(quest)
        quest["status"] = "active"

        bus.publish(TickAdvanced(turn_after=2))
        quest = world_repo.world.flags.get("quests", {}).get("supply_drop")
        self.assertEqual(1, quest["progress"])
        self.assertEqual("active", quest["status"])

        bus.publish(TickAdvanced(turn_after=3))
        quest = world_repo.world.flags.get("quests", {}).get("supply_drop")
        self.assertEqual(2, quest["progress"])
        self.assertEqual("ready_to_turn_in", quest["status"])


if __name__ == "__main__":
    unittest.main()
