import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class ReplayHarnessTests(unittest.TestCase):
    def _build_service(self) -> tuple[GameService, int]:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=123)
        character = Character(id=1, name="ReplayHero", class_name="fighter", level=2, location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})

        enemies = [
            Entity(id=10, name="Wolf", level=2, hp=8),
            Entity(id=11, name="Bandit", level=2, hp=9),
            Entity(id=12, name="Raider", level=2, hp=10),
        ]
        entity_repo = InMemoryEntityRepository(enemies)
        entity_repo.set_location_entities(1, [10, 11, 12])

        location_repo = InMemoryLocationRepository(
            {
                1: Location(
                    id=1,
                    name="Replay Plains",
                    factions=["wild"],
                    tags=["field"],
                )
            }
        )

        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )
        return service, character.id

    @staticmethod
    def _snapshot(service: GameService, character_id: int) -> dict:
        character = service._require_character(character_id)
        world = service._require_world()
        return {
            "world_turn": world.current_turn,
            "threat_level": world.threat_level,
            "character_hp": character.hp_current,
            "character_alive": character.alive,
            "character_xp": character.xp,
        }

    @staticmethod
    def _run_script(service: GameService, character_id: int, script: list[str]) -> dict:
        for action in script:
            if action == "explore":
                plan, player, _ = service.explore(character_id)
                if plan.enemies:
                    enemy = plan.enemies[0]
                    service.combat_resolve_intent(
                        player,
                        enemy,
                        lambda options, *_args, **_kwargs: "Attack" if "Attack" in options else options[0],
                        scene={"distance": "close", "terrain": "open", "surprise": "none"},
                    )
                    service.save_character_state(player)
            elif action == "rest":
                service.rest_intent(character_id)
            else:
                raise ValueError(f"Unknown action in replay script: {action}")
        return ReplayHarnessTests._snapshot(service, character_id)

    def test_replay_fixed_script_produces_same_snapshot(self) -> None:
        script = ["explore", "rest", "explore"]

        service_a, character_id_a = self._build_service()
        service_b, character_id_b = self._build_service()

        snapshot_a = self._run_script(service_a, character_id_a, script)
        snapshot_b = self._run_script(service_b, character_id_b, script)

        self.assertEqual(snapshot_a, snapshot_b)

    def test_replay_fixed_script_produces_same_encounter_sequence(self) -> None:
        script = ["explore", "explore", "explore"]

        service_a, character_id_a = self._build_service()
        service_b, character_id_b = self._build_service()

        seq_a: list[list[int]] = []
        seq_b: list[list[int]] = []

        for action in script:
            self.assertEqual("explore", action)
            plan_a, _, _ = service_a.explore(character_id_a)
            plan_b, _, _ = service_b.explore(character_id_b)
            seq_a.append([enemy.id for enemy in plan_a.enemies])
            seq_b.append([enemy.id for enemy in plan_b.enemies])

        self.assertEqual(seq_a, seq_b)

    def test_replay_memory_echo_is_deterministic_for_same_state(self) -> None:
        service_a, character_id_a = self._build_service()
        service_b, character_id_b = self._build_service()

        world_a = service_a._require_world()
        world_a.flags.setdefault("narrative", {})
        world_a.flags["narrative"]["major_events"] = [
            {
                "turn": 5,
                "seed_id": "seed_5_0042",
                "kind": "merchant_under_pressure",
                "resolution": "prosperity",
                "actor": character_id_a,
            }
        ]
        service_a.world_repo.save(world_a)

        world_b = service_b._require_world()
        world_b.flags.setdefault("narrative", {})
        world_b.flags["narrative"]["major_events"] = [
            {
                "turn": 5,
                "seed_id": "seed_5_0042",
                "kind": "merchant_under_pressure",
                "resolution": "prosperity",
                "actor": character_id_b,
            }
        ]
        service_b.world_repo.save(world_b)

        board_a = service_a.get_rumour_board_intent(character_id_a)
        board_b = service_b.get_rumour_board_intent(character_id_b)

        self.assertEqual([item.rumour_id for item in board_a.items], [item.rumour_id for item in board_b.items])
        self.assertEqual([item.text for item in board_a.items], [item.text for item in board_b.items])

    def test_replay_world_flag_peaceful_state_is_deterministic(self) -> None:
        service_a, character_id_a = self._build_service()
        service_b, character_id_b = self._build_service()

        world_a = service_a._require_world()
        world_a.flags.setdefault("world_flags", {})
        world_a.flags["world_flags"]["location:1:peaceful"] = True
        service_a.world_repo.save(world_a)

        world_b = service_b._require_world()
        world_b.flags.setdefault("world_flags", {})
        world_b.flags["world_flags"]["location:1:peaceful"] = True
        service_b.world_repo.save(world_b)

        script = ["explore", "explore", "rest"]
        snapshot_a = self._run_script(service_a, character_id_a, script)
        snapshot_b = self._run_script(service_b, character_id_b, script)

        self.assertEqual(snapshot_a, snapshot_b)


if __name__ == "__main__":
    unittest.main()
