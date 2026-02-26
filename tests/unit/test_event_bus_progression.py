import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.events import TickAdvanced
from rpg.domain.models.world import World
from rpg.domain.repositories import EntityRepository, WorldRepository


class _StubWorldRepository(WorldRepository):
    def __init__(self) -> None:
        self.saved = []
        self.world = World(id=1, name="Stubland", current_turn=0, rng_seed=7)

    def load_default(self) -> World:
        return self.world

    def save(self, world: World) -> None:
        self.saved.append(world)


class _StubEntityRepository(EntityRepository):
    def get(self, entity_id: int):
        return None

    def get_many(self, entity_ids: list[int]):
        return []

    def list_for_level(self, target_level: int, tolerance: int = 2):
        return []

    def list_by_location(self, location_id: int):
        return []


class EventBusTests(unittest.TestCase):
    def test_publish_notifies_all_handlers_for_event_type(self) -> None:
        bus = EventBus()
        seen: list[str] = []

        class ExampleEvent:
            pass

        bus.subscribe(ExampleEvent, lambda evt: seen.append("first"))
        bus.subscribe(ExampleEvent, lambda evt: seen.append("second"))

        bus.publish(ExampleEvent())

        self.assertEqual(["first", "second"], seen)

    def test_publish_filters_handlers_by_event_class(self) -> None:
        bus = EventBus()
        seen: list[str] = []

        class Alpha:
            pass

        class Beta:
            pass

        bus.subscribe(Alpha, lambda evt: seen.append("alpha"))
        bus.subscribe(Beta, lambda evt: seen.append("beta"))

        bus.publish(Alpha())

        self.assertEqual(["alpha"], seen)


class WorldProgressionTests(unittest.TestCase):
    def test_tick_advances_turns_and_persists_once(self) -> None:
        world_repo = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        events: list[TickAdvanced] = []
        bus = EventBus()
        bus.subscribe(TickAdvanced, lambda evt: events.append(evt))

        progression = WorldProgression(world_repo, entity_repo, bus)
        progression.tick(world_repo.world, ticks=3)

        self.assertEqual(3, world_repo.world.current_turn)
        self.assertEqual(1, len(world_repo.saved))
        self.assertEqual(1, len(events))
        self.assertEqual(3, events[0].turn_after)


if __name__ == "__main__":
    unittest.main()
