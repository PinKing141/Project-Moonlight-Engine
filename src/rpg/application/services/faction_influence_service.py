from __future__ import annotations

from rpg.application.services.event_bus import EventBus
from rpg.domain.events import MonsterSlain
from rpg.domain.repositories import EntityRepository, FactionRepository


class FactionInfluenceService:
    def __init__(
        self,
        faction_repo: FactionRepository,
        entity_repo: EntityRepository,
        event_bus: EventBus,
    ) -> None:
        self.faction_repo = faction_repo
        self.entity_repo = entity_repo
        self.event_bus = event_bus

    def register_handlers(self) -> None:
        self.event_bus.subscribe(MonsterSlain, self.on_monster_slain)

    def on_monster_slain(self, event: MonsterSlain) -> None:
        monster = self.entity_repo.get(event.monster_id)
        if monster is None or not monster.faction_id:
            return

        faction = self.faction_repo.get(monster.faction_id)
        if faction is None:
            return

        target = f"character:{event.by_character_id}"
        faction.adjust_reputation(target, -2)
        faction.influence = max(0, faction.influence - 1)
        self.faction_repo.save(faction)


def register_faction_influence_handlers(
    event_bus: EventBus,
    faction_repo: FactionRepository | None,
    entity_repo: EntityRepository | None,
) -> None:
    if faction_repo is None or entity_repo is None:
        return

    service = FactionInfluenceService(
        faction_repo=faction_repo,
        entity_repo=entity_repo,
        event_bus=event_bus,
    )
    service.register_handlers()
