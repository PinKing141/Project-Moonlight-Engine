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
        {
            "quest_id": "crown_hunt_order",
            "status": "available",
            "objective_kind": "kill_any",
            "progress": 0,
            "target": 2,
            "reward_xp": 18,
            "reward_money": 9,
        },
        {
            "quest_id": "syndicate_route_run",
            "status": "available",
            "objective_kind": "travel_count",
            "progress": 0,
            "target": 3,
            "reward_xp": 16,
            "reward_money": 10,
        },
        {
            "quest_id": "forest_path_clearance",
            "status": "available",
            "objective_kind": "kill_any",
            "progress": 0,
            "target": 3,
            "reward_xp": 20,
            "reward_money": 8,
        },
        {
            "quest_id": "ruins_wayfinding",
            "status": "available",
            "objective_kind": "travel_count",
            "progress": 0,
            "target": 2,
            "reward_xp": 14,
            "reward_money": 9,
        },
    )
    CATACLYSM_QUEST_TEMPLATES = (
        {
            "quest_id": "cataclysm_scout_front",
            "status": "available",
            "objective_kind": "kill_any",
            "progress": 0,
            "target": 3,
            "reward_xp": 26,
            "reward_money": 12,
            "cataclysm_pushback": True,
            "pushback_tier": 1,
        },
        {
            "quest_id": "cataclysm_supply_lines",
            "status": "available",
            "objective_kind": "travel_count",
            "progress": 0,
            "target": 2,
            "reward_xp": 24,
            "reward_money": 14,
            "cataclysm_pushback": True,
            "pushback_tier": 1,
        },
        {
            "quest_id": "cataclysm_alliance_accord",
            "status": "available",
            "objective_kind": "kill_any",
            "progress": 0,
            "target": 4,
            "reward_xp": 34,
            "reward_money": 18,
            "cataclysm_pushback": True,
            "pushback_tier": 2,
            "requires_alliance_reputation": 10,
            "requires_alliance_count": 2,
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
        self.event_bus.subscribe(TickAdvanced, self.on_tick_advanced, priority=20)
        self.event_bus.subscribe(MonsterSlain, self.on_monster_slain, priority=20)

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

        if self._is_cataclysm_active(world):
            self._sync_cataclysm_templates(world=world, quests=quests, world_turn=int(event.turn_after))
        else:
            self._sync_standard_templates(quests=quests, world_turn=int(event.turn_after))

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

    @staticmethod
    def _is_cataclysm_active(world) -> bool:
        if not isinstance(getattr(world, "flags", None), dict):
            return False
        state = world.flags.get("cataclysm_state", {})
        if not isinstance(state, dict):
            return False
        return bool(state.get("active", False))

    def _sync_standard_templates(self, *, quests: dict, world_turn: int) -> None:
        removable = [
            quest_id
            for quest_id, payload in quests.items()
            if isinstance(payload, dict)
            and bool(payload.get("cataclysm_pushback", False))
            and str(payload.get("status", "")) == "available"
        ]
        for quest_id in removable:
            quests.pop(quest_id, None)

        for template in self.QUEST_TEMPLATES:
            quest_id = str(template.get("quest_id", ""))
            if not quest_id or quest_id in quests:
                continue
            seed_value = derive_seed(
                namespace="quest.template",
                context={
                    "world_turn": int(world_turn),
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

    def _sync_cataclysm_templates(self, *, world, quests: dict, world_turn: int) -> None:
        state = world.flags.get("cataclysm_state", {}) if isinstance(world.flags, dict) else {}
        cat_seed = int(state.get("seed", 0) or 0) if isinstance(state, dict) else 0
        kind = str(state.get("kind", "") or "") if isinstance(state, dict) else ""
        phase = str(state.get("phase", "") or "") if isinstance(state, dict) else ""

        removable = [
            quest_id
            for quest_id, payload in quests.items()
            if isinstance(payload, dict)
            and not bool(payload.get("cataclysm_pushback", False))
            and str(payload.get("status", "")) == "available"
        ]
        for quest_id in removable:
            quests.pop(quest_id, None)

        for template in self.CATACLYSM_QUEST_TEMPLATES:
            quest_id = str(template.get("quest_id", ""))
            if not quest_id:
                continue
            existing = quests.get(quest_id)
            if isinstance(existing, dict) and str(existing.get("status", "")) in {
                "active",
                "ready_to_turn_in",
                "completed",
                "failed",
            }:
                continue
            seed_value = derive_seed(
                namespace="quest.cataclysm.template",
                context={
                    "cataclysm_seed": int(cat_seed),
                    "quest_id": quest_id,
                    "kind": kind,
                    "phase": phase,
                },
            )
            payload = dict(template)
            payload["seed_key"] = f"quest:{quest_id}:{int(seed_value)}"
            payload["spawned_turn"] = int(world_turn)
            payload["pushback_focus"] = kind
            payload["phase"] = phase
            quests[quest_id] = payload

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
