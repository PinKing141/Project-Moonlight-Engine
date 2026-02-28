from __future__ import annotations

from rpg.application.services.event_bus import EventBus
from rpg.domain.events import FactionReputationChangedEvent, MonsterSlain
from rpg.domain.repositories import CharacterRepository, EntityRepository, FactionRepository


class FactionInfluenceService:
    def __init__(
        self,
        faction_repo: FactionRepository,
        entity_repo: EntityRepository,
        event_bus: EventBus,
        character_repo: CharacterRepository | None = None,
    ) -> None:
        self.faction_repo = faction_repo
        self.entity_repo = entity_repo
        self.event_bus = event_bus
        self.character_repo = character_repo

    def _alignment_seed_delta(self, *, faction, character_id: int) -> int:
        if self.character_repo is None:
            return 0

        character = self.character_repo.get(int(character_id))
        if character is None:
            return 0

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        seeded = flags.setdefault("alignment_faction_seeded", {})
        if not isinstance(seeded, dict):
            seeded = {}
            flags["alignment_faction_seeded"] = seeded

        faction_id = str(getattr(faction, "id", "") or "").strip().lower()
        if not faction_id:
            return 0
        if faction_id in seeded:
            return 0

        alignment_value = str(getattr(character, "alignment", "") or "").strip().lower()
        delta = int(faction.alignment_affinity_delta(alignment_value))
        seeded[faction_id] = int(delta)
        self.character_repo.save(character)
        return int(delta)

    def register_handlers(self) -> None:
        self.event_bus.subscribe(MonsterSlain, self.on_monster_slain, priority=40)
        self.event_bus.subscribe(FactionReputationChangedEvent, self.on_faction_reputation_changed, priority=40)

    def on_monster_slain(self, event: MonsterSlain) -> None:
        monster = self.entity_repo.get(event.monster_id)
        if monster is None or not monster.faction_id:
            return

        self.event_bus.publish(
            FactionReputationChangedEvent(
                faction_id=str(monster.faction_id),
                character_id=int(event.by_character_id),
                delta=-2,
                reason="monster_slain",
                changed_turn=int(event.turn),
            )
        )

    def on_faction_reputation_changed(self, event: FactionReputationChangedEvent) -> None:
        faction = self.faction_repo.get(event.faction_id)
        if faction is None:
            return

        target = f"character:{int(event.character_id)}"
        seed_delta = self._alignment_seed_delta(faction=faction, character_id=int(event.character_id))
        if seed_delta != 0:
            faction.adjust_reputation(target, int(seed_delta))
        faction.adjust_reputation(target, int(event.delta))
        if int(event.delta) < 0:
            faction.influence = max(0, int(faction.influence) - 1)
        elif int(event.delta) > 0:
            faction.influence = max(0, int(faction.influence) + 1)
        self.faction_repo.save(faction)


def register_faction_influence_handlers(
    event_bus: EventBus,
    faction_repo: FactionRepository | None,
    entity_repo: EntityRepository | None,
    character_repo: CharacterRepository | None = None,
) -> None:
    if faction_repo is None or entity_repo is None:
        return

    service = FactionInfluenceService(
        faction_repo=faction_repo,
        entity_repo=entity_repo,
        event_bus=event_bus,
        character_repo=character_repo,
    )
    service.register_handlers()
