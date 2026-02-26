from __future__ import annotations

from rpg.application.services.balance_tables import (
    FIRST_HUNT_QUEST_ID,
    FIRST_HUNT_REWARD_MONEY,
    FIRST_HUNT_REWARD_XP,
    FIRST_HUNT_TARGET_KILLS,
)
from rpg.application.services.event_bus import EventBus
from rpg.application.services.seed_policy import derive_seed
from rpg.domain.events import MonsterSlain, TickAdvanced
from rpg.domain.repositories import CharacterRepository, WorldRepository


class QuestService:
    QUEST_ID = FIRST_HUNT_QUEST_ID
    QUEST_TEMPLATES = (
        {
            "quest_id": FIRST_HUNT_QUEST_ID,
            "status": "available",
            "objective_kind": "kill_any",
            "progress": 0,
            "target": FIRST_HUNT_TARGET_KILLS,
            "reward_xp": FIRST_HUNT_REWARD_XP,
            "reward_money": FIRST_HUNT_REWARD_MONEY,
        },
        {
            "quest_id": "trail_patrol",
            "status": "available",
            "objective_kind": "kill_any",
            "progress": 0,
            "target": 2,
            "reward_xp": 16,
            "reward_money": 7,
        },
        {
            "quest_id": "supply_drop",
            "status": "available",
            "objective_kind": "travel_count",
            "progress": 0,
            "target": 2,
            "reward_xp": 12,
            "reward_money": 8,
        },
    )

    def __init__(
        self,
        world_repo: WorldRepository,
        character_repo: CharacterRepository,
        event_bus: EventBus,
    ) -> None:
        self.world_repo = world_repo
        self.character_repo = character_repo
        self.event_bus = event_bus

    def register_handlers(self) -> None:
        self.event_bus.subscribe(TickAdvanced, self.on_tick_advanced)
        self.event_bus.subscribe(MonsterSlain, self.on_monster_slain)

    def on_tick_advanced(self, event: TickAdvanced) -> None:
        world = self.world_repo.load_default()
        if world is None:
            return

        if not isinstance(world.flags, dict):
            world.flags = {}

        quests = world.flags.setdefault("quests", {})
        for quest_id, quest in quests.items():
            if not isinstance(quest, dict) or quest.get("status") != "active":
                continue
            expires_turn = int(quest.get("expires_turn", event.turn_after + 1))
            if event.turn_after <= expires_turn:
                continue
            quest["status"] = "failed"
            quest["failed_turn"] = event.turn_after
            quest["failed_reason"] = "expired"
            self._append_consequence(
                world,
                message=f"You failed to finish {str(quest_id).replace('_', ' ').title()} in time.",
                kind="quest_expired",
                turn=event.turn_after,
            )

        if event.turn_after < 1:
            self.world_repo.save(world)
            return

        for template in self.QUEST_TEMPLATES:
            quest_id = str(template.get("quest_id", ""))
            if not quest_id or quest_id in quests:
                continue
            seed_value = derive_seed(
                namespace="quest.template",
                context={
                    "world_turn": int(event.turn_after),
                    "quest_id": quest_id,
                    "objective_kind": str(template.get("objective_kind", "kill_any")),
                },
            )
            quests[quest_id] = {
                "status": str(template.get("status", "available")),
                "objective_kind": str(template.get("objective_kind", "kill_any")),
                "progress": int(template.get("progress", 0)),
                "target": int(template.get("target", 1)),
                "reward_xp": int(template.get("reward_xp", 0)),
                "reward_money": int(template.get("reward_money", 0)),
                "seed_key": f"quest:{quest_id}:{int(seed_value)}",
            }

        for quest in quests.values():
            if not isinstance(quest, dict):
                continue
            if quest.get("status") != "active":
                continue
            if str(quest.get("objective_kind", "")) != "travel_count":
                continue
            progress = int(quest.get("progress", 0))
            target = max(1, int(quest.get("target", 1)))
            progress += 1
            quest["progress"] = min(progress, target)
            if progress >= target:
                quest["status"] = "ready_to_turn_in"
                quest["completed_turn"] = event.turn_after

        self.world_repo.save(world)

    def on_monster_slain(self, event: MonsterSlain) -> None:
        world = self.world_repo.load_default()
        if world is None or not isinstance(world.flags, dict):
            return

        quests = world.flags.setdefault("quests", {})
        touched = False
        for quest in quests.values():
            if not isinstance(quest, dict):
                continue
            if quest.get("status") != "active":
                continue
            if str(quest.get("objective_kind", "kill_any")) != "kill_any":
                continue

            progress = int(quest.get("progress", 0)) + 1
            target = max(1, int(quest.get("target", 1)))
            quest["progress"] = min(progress, target)
            quest["owner_character_id"] = event.by_character_id
            touched = True

            if progress < target:
                continue

            quest["status"] = "ready_to_turn_in"
            quest["completed_turn"] = event.turn

        if touched:
            self.world_repo.save(world)

    @staticmethod
    def _append_consequence(world, *, message: str, kind: str, turn: int) -> None:
        if not isinstance(world.flags, dict):
            world.flags = {}
        rows = world.flags.setdefault("consequences", [])
        if not isinstance(rows, list):
            rows = []
            world.flags["consequences"] = rows
        rows.append({"message": message, "kind": kind, "turn": int(turn), "severity": "normal"})
        if len(rows) > 20:
            del rows[:-20]


def register_quest_handlers(
    event_bus: EventBus,
    world_repo: WorldRepository | None,
    character_repo: CharacterRepository | None,
) -> None:
    if world_repo is None or character_repo is None:
        return

    service = QuestService(
        world_repo=world_repo,
        character_repo=character_repo,
        event_bus=event_bus,
    )
    service.register_handlers()
