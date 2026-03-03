import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.quest_service import register_quest_handlers
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.events import MonsterSlain
from rpg.domain.models.character import Character
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)
from rpg.infrastructure.inmemory.inmemory_faction_repo import InMemoryFactionRepository


class QuestArcFlowTests(unittest.TestCase):
    def _build_service(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=5)
        character = Character(id=41, name="Tamsin", location_id=1, xp=0, money=0)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        faction_repo = InMemoryFactionRepository()
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        register_quest_handlers(
            event_bus=event_bus,
            world_repo=world_repo,
            character_repo=character_repo,
        )

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
        )
        return service, event_bus, world_repo, character_repo, faction_repo, character.id

    def test_quest_arc_accept_progress_turn_in(self):
        service, event_bus, world_repo, character_repo, faction_repo, character_id = self._build_service()

        # Tick world once to seed quest board posting.
        service.advance_world(ticks=1)
        board = service.get_quest_board_intent(character_id)
        quest = next(q for q in board.quests if q.quest_id == "first_hunt")
        self.assertEqual("available", quest.status)

        accepted = service.accept_quest_intent(character_id, "first_hunt")
        self.assertIn("Accepted quest", " ".join(accepted.messages))

        # Progress quest through event hook.
        event_bus.publish(MonsterSlain(monster_id=9, location_id=1, by_character_id=character_id, turn=1))
        board = service.get_quest_board_intent(character_id)
        quest = next(q for q in board.quests if q.quest_id == "first_hunt")
        self.assertEqual("ready_to_turn_in", quest.status)

        hero = character_repo.get(character_id)
        hero.xp = 20
        character_repo.save(hero)

        result = service.turn_in_quest_intent(character_id, "first_hunt")
        self.assertIn("Turned in quest", " ".join(result.messages))
        self.assertIn("Level up!", " ".join(result.messages))

        hero = character_repo.get(character_id)
        self.assertGreater(hero.xp, 0)
        self.assertGreater(hero.money, 0)
        self.assertGreater(hero.level, 1)

        world = world_repo.load_default()
        first_hunt = world.flags.get("quests", {}).get("first_hunt", {})
        self.assertEqual("completed", first_hunt.get("status"))
        self.assertTrue(world.flags.get("quest_world_flags", {}).get("first_hunt_turned_in"))

        factions = faction_repo.list_all()
        target = f"character:{character_id}"
        self.assertTrue(any(faction.reputation.get(target, 0) > 0 for faction in factions))

    def test_cataclysm_board_replaces_available_normal_quests(self):
        service, _event_bus, world_repo, _character_repo, _faction_repo, character_id = self._build_service()
        world = world_repo.load_default()
        world.flags.setdefault("cataclysm_state", {})
        world.flags["cataclysm_state"].update(
            {
                "active": True,
                "kind": "plague",
                "phase": "grip_tightens",
                "progress": 54,
                "seed": 7001,
                "started_turn": 2,
                "last_advance_turn": world.current_turn,
            }
        )
        world_repo.save(world)

        service.advance_world(ticks=1)
        board = service.get_quest_board_intent(character_id)
        quest_ids = {item.quest_id for item in board.quests}

        self.assertIn("cataclysm_scout_front", quest_ids)
        self.assertIn("cataclysm_alliance_accord", quest_ids)
        self.assertNotIn("first_hunt", quest_ids)

    def test_cataclysm_alliance_quest_requires_standing_and_reduces_progress(self):
        service, event_bus, world_repo, _character_repo, faction_repo, character_id = self._build_service()
        world = world_repo.load_default()
        world.flags.setdefault("cataclysm_state", {})
        world.flags["cataclysm_state"].update(
            {
                "active": True,
                "kind": "tyrant",
                "phase": "map_shrinks",
                "progress": 66,
                "seed": 8080,
                "started_turn": 2,
                "last_advance_turn": world.current_turn,
            }
        )
        world_repo.save(world)
        service.advance_world(ticks=1)

        blocked = service.accept_quest_intent(character_id, "cataclysm_alliance_accord")
        self.assertTrue(any("alliance standing" in line.lower() for line in blocked.messages))

        factions = faction_repo.list_all()[:2]
        for faction in factions:
            faction.reputation[f"character:{character_id}"] = 12

        accepted = service.accept_quest_intent(character_id, "cataclysm_alliance_accord")
        self.assertTrue(any("Accepted quest" in line for line in accepted.messages))

        for _ in range(4):
            event_bus.publish(MonsterSlain(monster_id=9, location_id=1, by_character_id=character_id, turn=2))

        before = int(world_repo.load_default().flags.get("cataclysm_state", {}).get("progress", 0) or 0)
        result = service.turn_in_quest_intent(character_id, "cataclysm_alliance_accord")
        after = int(world_repo.load_default().flags.get("cataclysm_state", {}).get("progress", 0) or 0)

        self.assertTrue(any("doomsday progress" in line.lower() for line in result.messages))
        self.assertLess(after, before)

    def test_intervention_then_world_tick_shifts_quest_branch_visibility(self):
        service, _event_bus, world_repo, character_repo, _faction_repo, character_id = self._build_service()
        hero = character_repo.get(character_id)
        hero.money = 20
        hero.flags["faction_heat"] = {"wardens": 8}
        character_repo.save(hero)

        world = world_repo.load_default()
        world.flags.setdefault("quests", {})
        world.flags["quests"] = {
            "courier_run": {
                "status": "available",
                "objective_kind": "travel_to",
                "objective_target_location_id": 1,
                "progress": 0,
                "target": 1,
                "reward_xp": 14,
                "reward_money": 9,
                "seed_key": "quest:courier_run:101",
            }
        }
        world.flags["faction_conflict_v1"] = {
            "version": 1,
            "active": True,
            "relations": {
                "wardens|thieves_guild": {
                    "score": -4,
                    "stance": "hostile",
                    "last_updated_turn": int(getattr(world, "current_turn", 0) or 0),
                }
            },
            "last_tick_turn": int(getattr(world, "current_turn", 0) or 0),
        }
        world_repo.save(world)

        board_before = service.get_quest_board_intent(character_id)
        courier_before = next(q for q in board_before.quests if q.quest_id == "courier_run")
        self.assertIn("Arc Branch: Contested Routes", courier_before.objective_summary)

        with mock.patch("rpg.application.services.world_progression.derive_seed", return_value=1):
            relief = service.submit_pressure_relief_intent(character_id, faction_id="wardens")
            self.assertTrue(any("lay low" in line.lower() for line in relief.messages))
            service.advance_world(ticks=1)

        board_after = service.get_quest_board_intent(character_id)
        courier_after = next(q for q in board_after.quests if q.quest_id == "courier_run")
        self.assertIn("Arc Branch:", courier_after.objective_summary)
        self.assertNotIn("Contested Routes", courier_after.objective_summary)

        world_after = world_repo.load_default()
        quest_payload = dict((world_after.flags or {}).get("quests", {}).get("courier_run", {}))
        meta = dict(quest_payload.get("arc_metadata_v2", {}))
        self.assertEqual("frontier_routine", str(meta.get("branch_key", "") or ""))

    def test_replay_24_turns_keeps_faction_and_quest_arc_signatures_stable(self):
        service_a, _event_bus_a, repo_a, _character_repo_a, _faction_repo_a, character_id_a = self._build_service()
        service_b, _event_bus_b, repo_b, _character_repo_b, _faction_repo_b, character_id_b = self._build_service()

        for repo in (repo_a, repo_b):
            world = repo.load_default()
            world.flags.setdefault("faction_conflict_v1", {})
            world.flags["faction_conflict_v1"] = {
                "version": 1,
                "active": True,
                "relations": {
                    "wardens|thieves_guild": {
                        "score": -3,
                        "stance": "neutral",
                        "last_updated_turn": int(getattr(world, "current_turn", 0) or 0),
                    },
                    "the_crown|free_council": {
                        "score": 4,
                        "stance": "allied",
                        "last_updated_turn": int(getattr(world, "current_turn", 0) or 0),
                    },
                },
                "last_tick_turn": int(getattr(world, "current_turn", 0) or 0),
            }
            repo.save(world)

        def capture_signature(service: GameService, repo: InMemoryWorldRepository, character_id: int) -> list[tuple[int, tuple[str, int, str], tuple[tuple[str, int, str], ...]]]:
            timeline: list[tuple[int, tuple[str, int, str], tuple[tuple[str, int, str], ...]]] = []
            for _ in range(24):
                service.get_quest_board_intent(character_id)
                world = repo.load_default()
                turn = int(getattr(world, "current_turn", 0) or 0)

                state = dict((world.flags or {}).get("faction_conflict_v1", {}))
                relations = dict(state.get("relations", {}))
                top_pair = ""
                top_abs = -1
                top_stance = ""
                for raw_pair, raw_payload in relations.items():
                    payload = raw_payload if isinstance(raw_payload, dict) else {}
                    score_value = int(payload.get("score", 0) or 0)
                    abs_score = abs(score_value)
                    if abs_score > top_abs:
                        top_pair = str(raw_pair)
                        top_abs = abs_score
                        top_stance = str(payload.get("stance", "") or "")
                conflict_signature = (top_pair, int(top_abs), top_stance)

                quests = dict((world.flags or {}).get("quests", {}))
                quest_signature_rows: list[tuple[str, int, str]] = []
                for quest_id in sorted(quests.keys()):
                    payload = quests.get(quest_id)
                    if not isinstance(payload, dict):
                        continue
                    meta = payload.get("arc_metadata_v2", {})
                    if not isinstance(meta, dict):
                        continue
                    quest_signature_rows.append(
                        (
                            str(quest_id),
                            int(meta.get("signature", 0) or 0),
                            str(meta.get("branch_key", "") or ""),
                        )
                    )
                timeline.append((turn, conflict_signature, tuple(quest_signature_rows)))
                service.advance_world(ticks=1)
            return timeline

        timeline_a = capture_signature(service_a, repo_a, character_id_a)
        timeline_b = capture_signature(service_b, repo_b, character_id_b)

        self.assertEqual(24, len(timeline_a))
        self.assertEqual(timeline_a, timeline_b)
        self.assertTrue(any(bool(rows) for _, _, rows in timeline_a))


if __name__ == "__main__":
    unittest.main()
