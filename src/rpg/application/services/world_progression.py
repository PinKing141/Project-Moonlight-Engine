from rpg.domain.events import TickAdvanced
from rpg.domain.models.world import World
from rpg.domain.repositories import EntityRepository, WorldRepository
from .event_bus import EventBus


class WorldProgression:
    def __init__(self, world_repo: WorldRepository, entity_repo: EntityRepository, event_bus: EventBus) -> None:
        self.world_repo = world_repo
        self.entity_repo = entity_repo
        self.event_bus = event_bus

    def tick(self, world: World, ticks: int = 1, persist: bool = True) -> None:
        for _ in range(ticks):
            world.advance_turns()
            # Future hooks: NPC schedules, faction AI, story triggers
        if persist:
            self.world_repo.save(world)
        self.event_bus.publish(TickAdvanced(turn_after=world.current_turn))
