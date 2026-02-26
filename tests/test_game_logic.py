import random
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.events import MonsterSlain
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import EncounterTableEntry, Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class GameServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()

    def _build_service(
        self, character_repo, entity_repo, location_repo, world_repo
    ) -> GameService:
        progression = WorldProgression(world_repo, entity_repo, self.event_bus)
        return GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )

    def test_pick_monster_respects_level_ranges_and_weights(self) -> None:
        character = Character(id=1, name="Rogue", location_id=1, level=3)
        character_repo = InMemoryCharacterRepository({character.id: character})

        wolf = Entity(id=1, name="Wolf", level=2)
        dragon = Entity(id=2, name="Whelp", level=7)
        entity_repo = InMemoryEntityRepository([wolf, dragon])

        location = Location(
            id=1,
            name="Forest",
            encounters=[
                EncounterTableEntry(entity_id=1, weight=5, min_level=1, max_level=5),
                EncounterTableEntry(entity_id=2, weight=10, min_level=5, max_level=10),
            ],
        )
        location_repo = InMemoryLocationRepository({location.id: location})
        world_repo = InMemoryWorldRepository(seed=3)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        rng = random.Random(0)
        picked = service._pick_monster(character, location, rng)

        self.assertIsNotNone(picked)
        self.assertEqual(wolf.id, picked.id, "Higher level monsters should be filtered out")

    def test_combat_awards_xp_and_emits_event_on_kill(self) -> None:
        world_repo = InMemoryWorldRepository(seed=5)
        character = Character(id=7, name="Knight", location_id=2)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location = Location(id=2, name="Ruins")
        location_repo = InMemoryLocationRepository({location.id: location})

        slain_events: list[MonsterSlain] = []
        self.event_bus.subscribe(MonsterSlain, lambda event: slain_events.append(event))

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        world = world_repo.load_default()
        monster = Entity(id=99, name="Goblin", level=1, hp=1)

        rng = random.Random(11)
        message = service._resolve_combat(character, monster, rng, world, location)

        self.assertIn("falls", message)
        self.assertIn("gold", message)
        self.assertEqual(5, character.xp)
        self.assertEqual(2, character.money)
        self.assertEqual(1, len(slain_events))
        self.assertEqual(monster.id, slain_events[0].monster_id)

    def test_apply_encounter_reward_intent_returns_reward_view_and_persists(self) -> None:
        world_repo = InMemoryWorldRepository(seed=8)
        character = Character(id=4, name="Mira", location_id=1, xp=0, money=0)
        character_repo = InMemoryCharacterRepository({character.id: character})
        monster = Entity(id=8, name="Cultist", level=2, loot_tags=["ritual notes"])
        entity_repo = InMemoryEntityRepository([monster])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Sanctum")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        reward = service.apply_encounter_reward_intent(character, monster)

        self.assertEqual(10, reward.xp_gain)
        self.assertEqual(4, reward.money_gain)
        self.assertEqual(["ritual notes"], reward.loot_items)
        saved = character_repo.get(character.id)
        self.assertEqual(10, saved.xp)
        self.assertEqual(4, saved.money)
        self.assertIn("ritual notes", saved.inventory)

    def test_apply_encounter_reward_intent_levels_up_when_threshold_crossed(self) -> None:
        world_repo = InMemoryWorldRepository(seed=9)
        character = Character(id=14, name="Ryn", location_id=1, level=1, xp=20, hp_max=10, hp_current=7)
        character.attributes["constitution"] = 12
        character_repo = InMemoryCharacterRepository({character.id: character})
        monster = Entity(id=77, name="Shade", level=1)
        entity_repo = InMemoryEntityRepository([monster])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Hollow")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        service.apply_encounter_reward_intent(character, monster)

        saved = character_repo.get(character.id)
        self.assertEqual(2, saved.level)
        self.assertGreater(saved.hp_max, 10)
        self.assertGreater(saved.hp_current, 7)
        self.assertEqual(2, saved.flags.get("last_level_up", {}).get("to_level"))

    def test_combat_round_view_intent_contains_expected_payload(self) -> None:
        character = Character(id=5, name="Rook", class_name="rogue", hp_current=9, hp_max=12)
        character.flags = {"dodging": 1}
        character.spell_slots_current = 2
        character_repo = InMemoryCharacterRepository({character.id: character})
        enemy = Entity(id=10, name="Bandit", level=1, hp=7)
        enemy.intent = "aggressive"
        entity_repo = InMemoryEntityRepository([enemy])
        location_repo = InMemoryLocationRepository({})
        world_repo = InMemoryWorldRepository(seed=4)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        payload = service.combat_round_view_intent(
            options=["Attack", "Dodge", "Cast Spell"],
            player=character,
            enemy=enemy,
            round_no=2,
            scene_ctx={"distance": "mid", "terrain": "cramped", "surprise": "none"},
        )

        self.assertEqual(2, payload.round_number)
        self.assertEqual("mid", payload.scene.distance)
        self.assertEqual("cramped", payload.scene.terrain)
        self.assertEqual("none", payload.scene.surprise)
        self.assertEqual(character.hp_current, payload.player.hp_current)
        self.assertEqual("Yes", payload.player.sneak_ready)
        self.assertEqual("Dodging", payload.player.conditions)
        self.assertEqual("Bandit", payload.enemy.name)
        self.assertEqual("aggressive", payload.enemy.intent)
        self.assertEqual(["Attack", "Dodge", "Cast Spell"], payload.options)

    def test_submit_combat_action_intent_maps_actions(self) -> None:
        options = ["Attack", "Cast Spell", "Dodge"]

        self.assertEqual("Dodge", GameService.submit_combat_action_intent(options, -1))
        self.assertEqual("Dodge", GameService.submit_combat_action_intent(options, 99))
        self.assertEqual("Attack", GameService.submit_combat_action_intent(options, 0))
        self.assertEqual(
            ("Cast Spell", "magic-missile"),
            GameService.submit_combat_action_intent(options, 1, spell_slug="magic-missile"),
        )

    def test_submit_combat_action_intent_maps_use_item_with_selected_item(self) -> None:
        options = ["Attack", "Use Item", "Dodge"]

        self.assertEqual(
            ("Use Item", "Healing Herbs"),
            GameService.submit_combat_action_intent(options, 1, item_name="Healing Herbs"),
        )

    def test_get_character_sheet_intent_exposes_xp_progress(self) -> None:
        world_repo = InMemoryWorldRepository(seed=7)
        character = Character(
            id=29,
            name="Vale",
            location_id=1,
            class_name="fighter",
            level=2,
            xp=42,
            hp_max=18,
            hp_current=12,
            difficulty="normal",
        )
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        sheet = service.get_character_sheet_intent(character.id)

        self.assertEqual(2, sheet.level)
        self.assertEqual(42, sheet.xp)
        self.assertEqual(50, sheet.next_level_xp)
        self.assertEqual(8, sheet.xp_to_next_level)

    def test_encounter_plan_is_deterministic_for_same_context(self) -> None:
        character = Character(id=21, name="Scout", location_id=1, level=2)
        character_repo = InMemoryCharacterRepository({character.id: character})

        enemies = [
            Entity(id=1, name="Wolf", level=2, hp=8),
            Entity(id=2, name="Boar", level=2, hp=10),
            Entity(id=3, name="Bandit", level=2, hp=9),
        ]
        entity_repo = InMemoryEntityRepository(enemies)
        entity_repo.set_location_entities(1, [1, 2, 3])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Wilds")})
        world_repo = InMemoryWorldRepository(seed=7)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        plan_a = service.encounter_service.generate_plan(
            location_id=1,
            player_level=2,
            world_turn=3,
            faction_bias=None,
            max_enemies=2,
        )
        plan_b = service.encounter_service.generate_plan(
            location_id=1,
            player_level=2,
            world_turn=3,
            faction_bias=None,
            max_enemies=2,
        )

        self.assertEqual([entity.id for entity in plan_a.enemies], [entity.id for entity in plan_b.enemies])

    def test_combat_resolve_intent_is_deterministic_for_same_context(self) -> None:
        character_a = Character(id=30, name="Knight", class_name="fighter", location_id=1)
        character_b = Character(id=30, name="Knight", class_name="fighter", location_id=1)
        character_repo = InMemoryCharacterRepository({character_a.id: character_a})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Keep")})
        world_repo = InMemoryWorldRepository(seed=11)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        enemy_a = Entity(id=99, name="Goblin", level=1, hp=7)
        enemy_b = Entity(id=99, name="Goblin", level=1, hp=7)
        scene = {"distance": "close", "terrain": "open", "surprise": "none"}

        def choose_action(options, *_args, **_kwargs):
            return "Attack" if "Attack" in options else options[0]

        result_a = service.combat_resolve_intent(character_a, enemy_a, choose_action, scene=scene)
        result_b = service.combat_resolve_intent(character_b, enemy_b, choose_action, scene=scene)

        log_a = [entry.text for entry in result_a.log]
        log_b = [entry.text for entry in result_b.log]

        self.assertEqual(log_a, log_b)
        self.assertEqual(result_a.player.hp_current, result_b.player.hp_current)
        self.assertEqual(result_a.enemy.hp_current, result_b.enemy.hp_current)

        def test_combat_use_item_supports_healing_herbs(self) -> None:
            world_repo = InMemoryWorldRepository(seed=15)
            character = Character(id=44, name="Herbalist", class_name="rogue", location_id=1, hp_current=5, hp_max=12)
            character.inventory = ["Healing Herbs"]
            character_repo = InMemoryCharacterRepository({character.id: character})
            entity_repo = InMemoryEntityRepository([])
            location_repo = InMemoryLocationRepository({1: Location(id=1, name="Wilds")})

            service = self._build_service(
                character_repo=character_repo,
                entity_repo=entity_repo,
                location_repo=location_repo,
                world_repo=world_repo,
            )

            enemy = Entity(id=55, name="Rat", level=1, hp=4, hp_current=4, hp_max=4, attack_min=0, attack_max=1)
            used_item = {"done": False}

            def choose_action(options, *_args, **_kwargs):
                if not used_item["done"] and "Use Item" in options:
                    used_item["done"] = True
                    return "Use Item"
                return "Attack" if "Attack" in options else options[0]

            result = service.combat_resolve_intent(
                character,
                enemy,
                choose_action,
                scene={"distance": "close", "terrain": "open", "surprise": "player"},
            )

            self.assertNotIn("Healing Herbs", result.player.inventory)
            self.assertTrue(any("healing herbs" in entry.text.lower() for entry in result.log))
            self.assertGreaterEqual(result.player.hp_current, 5)

        def test_combat_use_item_honors_selected_item_when_multiple_are_available(self) -> None:
            world_repo = InMemoryWorldRepository(seed=16)
            character = Character(id=45, name="Scout", class_name="rogue", location_id=1, hp_current=6, hp_max=12)
            character.inventory = ["Healing Potion", "Healing Herbs"]
            character_repo = InMemoryCharacterRepository({character.id: character})
            entity_repo = InMemoryEntityRepository([])
            location_repo = InMemoryLocationRepository({1: Location(id=1, name="Wilds")})

            service = self._build_service(
                character_repo=character_repo,
                entity_repo=entity_repo,
                location_repo=location_repo,
                world_repo=world_repo,
            )

            enemy = Entity(id=56, name="Rat", level=1, hp=4, hp_current=4, hp_max=4, attack_min=0, attack_max=1)
            used_item = {"done": False}

            def choose_action(options, *_args, **_kwargs):
                if not used_item["done"] and "Use Item" in options:
                    used_item["done"] = True
                    return ("Use Item", "Healing Herbs")
                return "Attack" if "Attack" in options else options[0]

            result = service.combat_resolve_intent(
                character,
                enemy,
                choose_action,
                scene={"distance": "close", "terrain": "open", "surprise": "player"},
            )

            self.assertNotIn("Healing Herbs", result.player.inventory)
            self.assertIn("Healing Potion", result.player.inventory)
            self.assertTrue(any("healing herbs" in entry.text.lower() for entry in result.log))

    def test_flashpoint_pressure_adjusts_encounter_difficulty_context(self) -> None:
        character = Character(id=41, name="Ranger", location_id=1, level=2)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([
            Entity(id=1, name="Wolf", level=2, hp=8, faction_id="wild"),
            Entity(id=2, name="Warden Scout", level=3, hp=9, faction_id="wardens"),
        ])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Frontier", factions=["wild"])})
        world_repo = InMemoryWorldRepository(seed=19)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        world = world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["flashpoint_echoes"] = [
            {
                "turn": world.current_turn,
                "seed_id": "seed_1_7000",
                "resolution": "faction_shift",
                "channel": "combat",
                "bias_faction": "wardens",
                "rival_faction": "wild",
                "affected_factions": 3,
                "severity_score": 84,
                "severity_band": "critical",
            }
        ]
        world_repo.save(world)

        level, max_enemies, bias = service._encounter_flashpoint_adjustments(
            world,
            base_player_level=2,
            base_max_enemies=2,
            base_faction_bias="wild",
        )

        self.assertEqual(3, level)
        self.assertEqual(3, max_enemies)
        self.assertEqual("wardens", bias)

    def test_low_flashpoint_pressure_keeps_base_encounter_context(self) -> None:
        character = Character(id=42, name="Scout", location_id=1, level=2)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([
            Entity(id=1, name="Wolf", level=2, hp=8, faction_id="wild"),
        ])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Frontier", factions=["wild"])})
        world_repo = InMemoryWorldRepository(seed=20)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        world = world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["flashpoint_echoes"] = [
            {
                "turn": world.current_turn - 10,
                "seed_id": "seed_0_1000",
                "resolution": "prosperity",
                "channel": "social",
                "bias_faction": "wardens",
                "rival_faction": "wild",
                "affected_factions": 1,
                "severity_score": 20,
                "severity_band": "low",
            }
        ]
        world_repo.save(world)

        level, max_enemies, bias = service._encounter_flashpoint_adjustments(
            world,
            base_player_level=2,
            base_max_enemies=2,
            base_faction_bias="wild",
        )

        self.assertEqual(2, level)
        self.assertEqual(2, max_enemies)
        self.assertEqual("wild", bias)


if __name__ == "__main__":
    unittest.main()
