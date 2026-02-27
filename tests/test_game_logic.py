import random
import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.application.services.combat_service import CombatResult
from rpg.application.dtos import EncounterPlan
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

        self.assertIn("defeat", message.lower())
        self.assertIn("gold", message)
        self.assertEqual(5, character.xp)
        self.assertEqual(2, character.money)
        self.assertEqual(1, len(slain_events))
        self.assertEqual(monster.id, slain_events[0].monster_id)

    def test_resolve_combat_routes_through_combat_service_engine(self) -> None:
        world_repo = InMemoryWorldRepository(seed=5)
        character = Character(id=7, name="Knight", location_id=2)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location = Location(id=2, name="Ruins")
        location_repo = InMemoryLocationRepository({location.id: location})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        world = world_repo.load_default()
        monster = Entity(id=99, name="Goblin", level=1, hp=1)
        seen_actions: list[str] = []

        def _fake_fight(player, enemy, choose_action, scene=None):
            choice = choose_action(["Attack"], player, enemy, 1, scene or {})
            if isinstance(choice, tuple):
                seen_actions.append(str(choice[0]))
            else:
                seen_actions.append(str(choice))
            won_player = Character(
                id=player.id,
                name=player.name,
                level=player.level,
                xp=player.xp,
                money=player.money,
                hp_max=player.hp_max,
                hp_current=player.hp_current,
                class_name=player.class_name,
                base_attributes=dict(player.base_attributes),
                location_id=player.location_id,
                attack_min=player.attack_min,
                attack_max=player.attack_max,
                attack_bonus=player.attack_bonus,
                damage_die=player.damage_die,
                armour_class=player.armour_class,
                armor=player.armor,
                alive=player.alive,
                character_type_id=player.character_type_id,
                attributes=dict(player.attributes),
                faction_id=player.faction_id,
                inventory=list(player.inventory),
                race=player.race,
                race_traits=list(player.race_traits),
                speed=player.speed,
                background=player.background,
                background_features=list(player.background_features),
                proficiencies=list(player.proficiencies),
                difficulty=player.difficulty,
                flags=dict(player.flags),
                incoming_damage_multiplier=player.incoming_damage_multiplier,
                outgoing_damage_multiplier=player.outgoing_damage_multiplier,
                spell_slots_max=player.spell_slots_max,
                spell_slots_current=player.spell_slots_current,
                cantrips=list(player.cantrips),
                known_spells=list(player.known_spells),
            )
            defeated_enemy = Entity(id=enemy.id, name=enemy.name, level=enemy.level, hp=enemy.hp, hp_current=0, hp_max=enemy.hp)
            return CombatResult(player=won_player, enemy=defeated_enemy, log=[], player_won=True)

        with mock.patch.object(service.combat_service, "fight_turn_based", side_effect=_fake_fight) as patched:
            message = service._resolve_combat(character, monster, random.Random(11), world, location)

        self.assertTrue(patched.called)
        self.assertEqual(["Attack"], seen_actions)
        self.assertIn("defeat", message.lower())

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

    def test_apply_encounter_reward_intent_can_drop_new_utility_consumables(self) -> None:
        world_repo = InMemoryWorldRepository(seed=8)
        world = world_repo.load_default()
        world.current_turn = 3
        world_repo.save(world)
        character = Character(id=2, name="Nox", location_id=1, xp=0, money=0)
        character_repo = InMemoryCharacterRepository({character.id: character})
        monster = Entity(id=1, name="Sentry", level=1)
        entity_repo = InMemoryEntityRepository([monster])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Gate")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        reward = service.apply_encounter_reward_intent(character, monster)

        self.assertIn("Focus Potion", reward.loot_items)
        saved = character_repo.get(character.id)
        self.assertIn("Focus Potion", saved.inventory)

    def test_apply_encounter_reward_intent_can_drop_tiered_item(self) -> None:
        world_repo = InMemoryWorldRepository(seed=8)
        world = world_repo.load_default()
        world.current_turn = 5
        world_repo.save(world)

        character = Character(id=6, name="Kara", location_id=1, xp=0, money=0)
        character_repo = InMemoryCharacterRepository({character.id: character})
        monster = Entity(id=12, name="Mercenary", level=4)
        entity_repo = InMemoryEntityRepository([monster])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Road")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        with mock.patch("rpg.application.services.game_service.derive_seed", side_effect=[2, 101]):
            reward = service.apply_encounter_reward_intent(character, monster)

        self.assertIn("Antitoxin", reward.loot_items)
        saved = character_repo.get(character.id)
        self.assertIn("Antitoxin", saved.inventory)

    def test_shop_view_includes_new_utility_items(self) -> None:
        world_repo = InMemoryWorldRepository(seed=3)
        character = Character(id=21, name="Lio", location_id=1, money=120)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        shop = service.get_shop_view_intent(character.id)
        names = {item.name for item in shop.items}
        self.assertIn("Torch", names)
        self.assertIn("Rope", names)
        self.assertIn("Climbing Kit", names)
        self.assertIn("Antitoxin", names)

    def test_cataclysm_state_is_normalized_and_persisted_on_read(self) -> None:
        world_repo = InMemoryWorldRepository(seed=3)
        world = world_repo.load_default()
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "unknown_kind",
            "phase": "invalid_phase",
            "progress": 177,
            "seed": -3,
            "started_turn": -1,
            "last_advance_turn": -9,
        }

        normalized = GameService._world_cataclysm_state(world)
        self.assertTrue(bool(normalized["active"]))
        self.assertEqual("", str(normalized["kind"]))
        self.assertEqual("", str(normalized["phase"]))
        self.assertEqual(100, int(normalized["progress"]))
        self.assertEqual(0, int(normalized["seed"]))
        self.assertEqual(0, int(normalized["started_turn"]))
        self.assertEqual(0, int(normalized["last_advance_turn"]))

        persisted = world.flags.get("cataclysm_state", {})
        self.assertIsInstance(persisted, dict)
        self.assertEqual(100, int(persisted.get("progress", 0) or 0))

    def test_game_loop_and_town_views_surface_cataclysm_summary(self) -> None:
        world_repo = InMemoryWorldRepository(seed=3)
        world = world_repo.load_default()
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "plague",
            "phase": "grip_tightens",
            "progress": 48,
            "seed": 1234,
            "started_turn": 4,
            "last_advance_turn": 7,
        }
        world_repo.save(world)

        character = Character(id=99, name="Rhea", location_id=1)
        character_repo = InMemoryCharacterRepository({99: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        loop_view = service.get_game_loop_view(99)
        self.assertTrue(loop_view.cataclysm_active)
        self.assertEqual("plague", loop_view.cataclysm_kind)
        self.assertEqual("grip_tightens", loop_view.cataclysm_phase)
        self.assertEqual(48, int(loop_view.cataclysm_progress))
        self.assertIn("Plague", loop_view.cataclysm_summary)

        town_view = service.get_town_view_intent(99)
        self.assertTrue(town_view.cataclysm_active)
        self.assertEqual("plague", town_view.cataclysm_kind)
        self.assertEqual("grip_tightens", town_view.cataclysm_phase)
        self.assertEqual(48, int(town_view.cataclysm_progress))
        self.assertIn("Grip Tightens", town_view.cataclysm_summary)

    def test_cataclysm_quest_pushback_reduction_is_deterministic(self) -> None:
        def _build_world_repo(seed: int) -> InMemoryWorldRepository:
            repo = InMemoryWorldRepository(seed=seed)
            world = repo.load_default()
            world.current_turn = 9
            world.flags["cataclysm_state"] = {
                "active": True,
                "kind": "demon_king",
                "phase": "grip_tightens",
                "progress": 64,
                "seed": 9102,
                "started_turn": 3,
                "last_advance_turn": 8,
            }
            repo.save(world)
            return repo

        quest_payload = {
            "cataclysm_pushback": True,
            "pushback_tier": 2,
        }

        service_a = self._build_service(
            character_repo=InMemoryCharacterRepository({1: Character(id=1, name="A", location_id=1)}),
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=_build_world_repo(seed=302),
        )
        service_b = self._build_service(
            character_repo=InMemoryCharacterRepository({1: Character(id=1, name="A", location_id=1)}),
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=_build_world_repo(seed=302),
        )

        world_a = service_a.world_repo.load_default()
        world_b = service_b.world_repo.load_default()
        reduction_a = service_a._apply_cataclysm_pushback_from_quest(
            world_a,
            quest_id="cataclysm_alliance_accord",
            quest=dict(quest_payload),
            character_id=1,
        )
        reduction_b = service_b._apply_cataclysm_pushback_from_quest(
            world_b,
            quest_id="cataclysm_alliance_accord",
            quest=dict(quest_payload),
            character_id=1,
        )

        self.assertEqual(reduction_a, reduction_b)
        self.assertEqual(
            int(world_a.flags.get("cataclysm_state", {}).get("progress", 0) or 0),
            int(world_b.flags.get("cataclysm_state", {}).get("progress", 0) or 0),
        )

    def test_cataclysm_apex_objective_spawns_at_threshold(self) -> None:
        world_repo = InMemoryWorldRepository(seed=401)
        world = world_repo.load_default()
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "tyrant",
            "phase": "map_shrinks",
            "progress": 20,
            "seed": 2201,
            "started_turn": 3,
            "last_advance_turn": world.current_turn,
        }
        world_repo.save(world)

        character = Character(id=501, name="Vale", location_id=1)
        service = self._build_service(
            character_repo=InMemoryCharacterRepository({character.id: character}),
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )

        board = service.get_quest_board_intent(character.id)
        quest_ids = {row.quest_id for row in board.quests}

        self.assertIn("cataclysm_apex_clash", quest_ids)

    def test_world_fell_end_state_persists_and_surfaces_terminal_intent(self) -> None:
        world_repo = InMemoryWorldRepository(seed=402)
        world = world_repo.load_default()
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "demon_king",
            "phase": "ruin",
            "progress": 100,
            "seed": 2202,
            "started_turn": 2,
            "last_advance_turn": world.current_turn,
        }
        world_repo.save(world)

        character = Character(id=502, name="Vale", location_id=1)
        service = self._build_service(
            character_repo=InMemoryCharacterRepository({character.id: character}),
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )

        terminal = service.get_cataclysm_terminal_state_intent(character.id)
        self.assertIsNotNone(terminal)
        game_over, message = terminal or (False, "")
        self.assertTrue(game_over)
        self.assertIn("World Fell", message)

        saved_world = world_repo.load_default()
        end_state = saved_world.flags.get("cataclysm_end_state", {})
        self.assertEqual("world_fell", str(end_state.get("status", "")))
        self.assertTrue(bool(end_state.get("game_over", False)))

    def test_hazard_resolution_consumes_matching_utility_item(self) -> None:
        world_repo = InMemoryWorldRepository(seed=4)
        character = Character(id=31, name="Nia", location_id=1, hp_current=12, hp_max=12)
        character.inventory = ["Torch"]
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Cavern Mouth", biome="wilderness")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        plan = EncounterPlan(enemies=[], hazards=["Dark Cave"])
        message, _ = service._resolve_explore_hazard(character, plan)

        self.assertNotIn("Torch", character.inventory)
        self.assertIn("Torchlight", message)

    def test_wilderness_scout_uses_wisdom_check_and_can_reduce_threat(self) -> None:
        world_repo = InMemoryWorldRepository(seed=10)
        world = world_repo.load_default()
        world.current_turn = 7
        world.threat_level = 4
        world_repo.save(world)

        character = Character(id=40, name="Ari", location_id=1)
        character.attributes["wisdom"] = 16
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Ridge")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        with mock.patch("rpg.application.services.game_service.derive_seed", return_value=1), mock.patch("random.Random.randint", return_value=20):
            result = service.wilderness_action_intent(character.id, "scout")

        self.assertTrue(any("Survival check" in line for line in result.messages))
        self.assertTrue(any("lower local pressure" in line for line in result.messages))
        updated_world = world_repo.load_default()
        self.assertEqual(3, int(getattr(updated_world, "threat_level", 0) or 0))

    def test_wilderness_sneak_sets_next_explore_surprise_and_consumes(self) -> None:
        world_repo = InMemoryWorldRepository(seed=11)
        character = Character(id=41, name="Vale", location_id=1)
        character.attributes["dexterity"] = 18
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Pines")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        with mock.patch("rpg.application.services.game_service.derive_seed", return_value=1), mock.patch("random.Random.randint", return_value=20):
            result = service.wilderness_action_intent(character.id, "sneak")

        self.assertTrue(any("Stealth check" in line for line in result.messages))
        self.assertTrue(any("next encounter starts with surprise" in line for line in result.messages))

        first = service.consume_next_explore_surprise_intent(character.id)
        second = service.consume_next_explore_surprise_intent(character.id)
        self.assertEqual("player", first)
        self.assertIsNone(second)

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

    def test_combat_round_view_includes_active_status_conditions(self) -> None:
        character = Character(id=15, name="Mira", class_name="wizard", hp_current=10, hp_max=12)
        character.flags = {
            "combat_statuses": [
                {"id": "burning", "rounds": 2, "potency": 1},
                {"id": "blessed", "rounds": 1, "potency": 1},
            ]
        }
        character_repo = InMemoryCharacterRepository({character.id: character})
        enemy = Entity(id=18, name="Raider", level=1, hp=8)
        entity_repo = InMemoryEntityRepository([enemy])

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=InMemoryLocationRepository({}),
            world_repo=InMemoryWorldRepository(seed=12),
        )

        payload = service.combat_round_view_intent(
            options=["Attack"],
            player=character,
            enemy=enemy,
            round_no=1,
            scene_ctx={},
        )

        self.assertIn("Burning(2)", payload.player.conditions)
        self.assertIn("Blessed(1)", payload.player.conditions)

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

    def test_submit_combat_action_intent_maps_new_consumables(self) -> None:
        options = ["Attack", "Use Item", "Dodge"]

        self.assertEqual(
            ("Use Item", "Focus Potion"),
            GameService.submit_combat_action_intent(options, 1, item_name="Focus Potion"),
        )
        self.assertEqual(
            ("Use Item", "Whetstone"),
            GameService.submit_combat_action_intent(options, 1, item_name="Whetstone"),
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

    def test_character_sheet_includes_faction_pressure_summary(self) -> None:
        world_repo = InMemoryWorldRepository(seed=26)
        character = Character(id=60, name="Vale", location_id=1, hp_max=18, hp_current=12)
        character.flags["faction_heat"] = {"wardens": 12, "thieves_guild": 5}
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

        self.assertIn("Pressure:", sheet.pressure_summary)
        self.assertTrue(any("Wardens" in line for line in sheet.pressure_lines))

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

    def test_cataclysm_phase_applies_explore_encounter_pressure(self) -> None:
        world_repo = InMemoryWorldRepository(seed=201)
        world = world_repo.load_default()
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "tyrant",
            "phase": "ruin",
            "progress": 96,
            "seed": 122,
            "started_turn": 5,
            "last_advance_turn": world.current_turn,
        }
        world_repo.save(world)

        character = Character(id=401, name="Rin", location_id=1, level=2)
        service = self._build_service(
            character_repo=InMemoryCharacterRepository({character.id: character}),
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Frontier", factions=["wild"])}),
            world_repo=world_repo,
        )

        level, max_enemies, bias = service._encounter_flashpoint_adjustments(
            world,
            base_player_level=2,
            base_max_enemies=2,
            base_faction_bias="wild",
        )

        self.assertEqual(4, level)
        self.assertEqual(3, max_enemies)
        self.assertEqual("the_crown", bias)

    def test_faction_heat_pressure_raises_travel_risk_hint(self) -> None:
        character = Character(id=50, name="Dane", location_id=1, level=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Road")})
        world_repo = InMemoryWorldRepository(seed=21)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        with mock.patch("random.Random.randint", return_value=30):
            base = service._travel_risk_hint(
                character_id=character.id,
                world_turn=1,
                threat_level=1,
                location_id=1,
                location_name="Road",
                recommended_level=1,
            )

        character.flags["faction_heat"] = {"wardens": 20}
        service.character_repo.save(character)

        with mock.patch("random.Random.randint", return_value=30):
            heated = service._travel_risk_hint(
                character_id=character.id,
                world_turn=1,
                threat_level=1,
                location_id=1,
                location_name="Road",
                recommended_level=1,
            )

        self.assertEqual("Low", base)
        self.assertEqual("Moderate", heated)

    def test_biome_severity_raises_travel_risk_hint(self) -> None:
        character = Character(id=150, name="Tarin", location_id=1, level=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Green Road", biome="temperate_deciduous_forest"),
                2: Location(id=2, name="Ice Pass", biome="glacier"),
            }
        )
        world_repo = InMemoryWorldRepository(seed=121)
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        dataset = type(
            "DatasetStub",
            (),
            {"biome_severity_index": {"temperate_deciduous_forest": 20, "glacier": 95}},
        )()
        with mock.patch.object(GameService, "_load_reference_world_dataset_cached", return_value=dataset):
            with mock.patch("random.Random.randint", return_value=39):
                low_risk = service._travel_risk_hint(
                    character_id=character.id,
                    world_turn=1,
                    threat_level=1,
                    location_id=1,
                    location_name="Green Road",
                    recommended_level=1,
                )
            with mock.patch("random.Random.randint", return_value=39):
                high_risk = service._travel_risk_hint(
                    character_id=character.id,
                    world_turn=1,
                    threat_level=1,
                    location_id=2,
                    location_name="Ice Pass",
                    recommended_level=1,
                )

        self.assertEqual("Low", low_risk)
        self.assertEqual("Moderate", high_risk)

    def test_biome_severity_increases_explore_hazard_dc(self) -> None:
        character = Character(id=151, name="Kira", location_id=1, level=1, hp_max=20, hp_current=20)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Wilds", biome="forest")})
        world_repo = InMemoryWorldRepository(seed=122)
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )
        plan = EncounterPlan(enemies=[], hazards=["Falling Rocks"], source="table")

        low_dataset = type("DatasetLow", (), {"biome_severity_index": {"forest": 10}})()
        high_dataset = type("DatasetHigh", (), {"biome_severity_index": {"forest": 95}})()

        with mock.patch("random.Random.randint", return_value=13):
            with mock.patch.object(GameService, "_load_reference_world_dataset_cached", return_value=low_dataset):
                low_message, low_skip = service._resolve_explore_hazard(character, plan)

        character.hp_current = character.hp_max
        with mock.patch("random.Random.randint", return_value=13):
            with mock.patch.object(GameService, "_load_reference_world_dataset_cached", return_value=high_dataset):
                high_message, high_skip = service._resolve_explore_hazard(character, plan)

        self.assertIn("safely", low_message)
        self.assertFalse(low_skip)
        self.assertIn("strains your advance", high_message)
        self.assertFalse(high_skip)

    def test_explore_applies_dominant_faction_heat_as_bias(self) -> None:
        character = Character(id=51, name="Moss", location_id=1, level=2)
        character.flags["faction_heat"] = {"wardens": 8}
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {1: Location(id=1, name="Frontier", factions=["wild"]) }
        )
        world_repo = InMemoryWorldRepository(seed=22)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        with mock.patch.object(
            service.encounter_service,
            "generate_plan",
            return_value=EncounterPlan(enemies=[], source="table"),
        ) as generate_plan:
            service.explore(character.id)

        called_bias = generate_plan.call_args.kwargs.get("faction_bias")
        self.assertEqual("wardens", called_bias)

    def test_town_price_modifier_includes_faction_heat_pressure(self) -> None:
        character = Character(id=52, name="Bram", location_id=1, level=1)
        character.flags["faction_heat"] = {"thieves_guild": 10}
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        world_repo = InMemoryWorldRepository(seed=23)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        modifier = service._town_price_modifier(character.id)

        self.assertEqual(5, modifier)

    def test_shop_view_labels_pressure_source_when_surcharged(self) -> None:
        world_repo = InMemoryWorldRepository(seed=27)
        character = Character(id=61, name="Bram", location_id=1, level=1, money=50)
        character.flags["faction_heat"] = {"thieves_guild": 12}
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        shop = service.get_shop_view_intent(character.id)

        self.assertIn("pressure", shop.price_modifier_label.lower())
        self.assertIn("thieves guild", shop.price_modifier_label.lower())

    def test_rest_decays_faction_heat_and_records_log(self) -> None:
        world_repo = InMemoryWorldRepository(seed=24)
        character = Character(id=53, name="Mira", location_id=1, hp_current=4, hp_max=10)
        character.flags["faction_heat"] = {"wardens": 6}
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        service.rest(character.id)

        saved = character_repo.get(character.id)
        self.assertIsNotNone(saved)
        heat = dict(saved.flags.get("faction_heat", {}))
        self.assertEqual(4, int(heat.get("wardens", 0)))
        history = list(saved.flags.get("faction_heat_log", []))
        self.assertTrue(history)
        self.assertEqual("rest", str(history[-1].get("reason", "")))

    def test_travel_faction_heat_decay_respects_interval(self) -> None:
        world_repo = InMemoryWorldRepository(seed=25)
        player = Character(id=54, name="Ari", class_name="fighter", location_id=1)
        player.flags["faction_heat"] = {"thieves_guild": 5}
        character_repo = InMemoryCharacterRepository({player.id: player})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Town", biome="village", x=0.0, y=0.0),
                2: Location(id=2, name="Wilds", biome="forest", x=100.0, y=0.0),
            }
        )

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        service.travel_intent(player.id, destination_id=2, travel_mode="road")

        saved = character_repo.get(player.id)
        self.assertIsNotNone(saved)
        heat = dict(saved.flags.get("faction_heat", {}))
        self.assertEqual(3, int(heat.get("thieves_guild", 0)))
        history = [entry for entry in list(saved.flags.get("faction_heat_log", [])) if str(entry.get("reason", "")) == "travel"]
        self.assertEqual(2, len(history))

    def test_pressure_relief_reduces_selected_faction_heat_and_spends_day_and_gold(self) -> None:
        world_repo = InMemoryWorldRepository(seed=28)
        world = world_repo.load_default()
        start_turn = int(getattr(world, "current_turn", 0) or 0)
        character = Character(id=62, name="Nyx", location_id=1, money=20)
        character.flags["faction_heat"] = {"wardens": 9, "thieves_guild": 4}
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        result = service.submit_pressure_relief_intent(character.id, faction_id="wardens")

        saved = character_repo.get(character.id)
        self.assertIsNotNone(saved)
        self.assertEqual(14, int(saved.money))
        heat = dict(saved.flags.get("faction_heat", {}))
        self.assertEqual(6, int(heat.get("wardens", 0)))
        relief_rows = [row for row in list(saved.flags.get("faction_heat_log", [])) if str(row.get("reason", "")) == "relief"]
        self.assertTrue(relief_rows)
        updated_world = world_repo.load_default()
        self.assertEqual(start_turn + 1, int(getattr(updated_world, "current_turn", 0) or 0))
        self.assertTrue(any("lay low" in line.lower() for line in result.messages))

    def test_pressure_relief_requires_gold(self) -> None:
        world_repo = InMemoryWorldRepository(seed=29)
        character = Character(id=63, name="Ryn", location_id=1, money=2)
        character.flags["faction_heat"] = {"wardens": 8}
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        result = service.submit_pressure_relief_intent(character.id, faction_id="wardens")

        saved = character_repo.get(character.id)
        self.assertIsNotNone(saved)
        self.assertEqual(2, int(saved.money))
        self.assertEqual(8, int(dict(saved.flags.get("faction_heat", {})).get("wardens", 0)))
        self.assertTrue(any("need" in line.lower() and "gold" in line.lower() for line in result.messages))

    def test_explore_applies_faction_encounter_hazard_package(self) -> None:
        character = Character(id=64, name="Kest", location_id=1, level=2)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Backstreets", factions=["thieves_guild"])})
        world_repo = InMemoryWorldRepository(seed=30)

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        with mock.patch.object(
            service.encounter_service,
            "generate_plan",
            return_value=EncounterPlan(enemies=[], hazards=[]),
        ), mock.patch("rpg.application.services.game_service.derive_seed", return_value=1):
            plan, _, _ = service.explore(character.id)

        self.assertIn("Hidden Snare", list(plan.hazards or []))

    def test_apply_encounter_reward_intent_applies_faction_money_tilt(self) -> None:
        world_repo = InMemoryWorldRepository(seed=31)
        character = Character(id=65, name="Nara", location_id=1, xp=0, money=0)
        character_repo = InMemoryCharacterRepository({character.id: character})
        monster = Entity(id=66, name="Cutpurse", level=1, faction_id="thieves_guild", loot_tags=["stolen map"])
        entity_repo = InMemoryEntityRepository([monster])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Alleys")})

        service = self._build_service(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
        )

        reward = service.apply_encounter_reward_intent(character, monster)

        self.assertEqual(4, reward.money_gain)
        saved = character_repo.get(character.id)
        self.assertEqual(4, int(saved.money))

    def test_post_combat_morale_consequence_triggers_and_reduces_threat(self) -> None:
        world_repo = InMemoryWorldRepository(seed=32)
        world = world_repo.load_default()
        world.threat_level = 4
        world.current_turn = 9
        world_repo.save(world)

        character = Character(id=70, name="Ari", location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Frontier")}),
            world_repo=world_repo,
        )

        with mock.patch("rpg.application.services.game_service.derive_seed", return_value=1):
            triggered = service._apply_post_combat_morale_consequence(
                world=world,
                character_id=character.id,
                world_turn=9,
                allies_won=True,
                fled=False,
                enemy_factions=["wardens"],
                context_key="party",
            )

        self.assertTrue(triggered)
        self.assertEqual(3, int(getattr(world, "threat_level", 0) or 0))
        messages = service._recent_consequence_messages(world, limit=1)
        self.assertTrue(any("wardens" in line.lower() for line in messages))

    def test_post_combat_morale_consequence_does_not_trigger_when_roll_fails(self) -> None:
        world_repo = InMemoryWorldRepository(seed=33)
        world = world_repo.load_default()
        world.threat_level = 4
        world.current_turn = 9
        world_repo.save(world)

        character = Character(id=71, name="Ari", location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Frontier")}),
            world_repo=world_repo,
        )

        with mock.patch("rpg.application.services.game_service.derive_seed", return_value=99):
            triggered = service._apply_post_combat_morale_consequence(
                world=world,
                character_id=character.id,
                world_turn=9,
                allies_won=True,
                fled=False,
                enemy_factions=["wardens"],
                context_key="party",
            )

        self.assertFalse(triggered)
        self.assertEqual(4, int(getattr(world, "threat_level", 0) or 0))

    def test_no_combat_fallback_rope_counter_reduces_hp_and_threat(self) -> None:
        world_repo = InMemoryWorldRepository(seed=34)
        world = world_repo.load_default()
        world.threat_level = 0
        world_repo.save(world)

        character = Character(id=72, name="Ari", location_id=1, hp_current=12, hp_max=24)
        character.inventory = ["Rope"]
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Road")}),
            world_repo=world_repo,
        )

        with mock.patch("random.Random.randint", return_value=20):
            message = service._apply_explore_no_combat_fallback(character, [Entity(id=1, name="Scout", level=1)])

        self.assertIn("rope line", message.lower())
        self.assertEqual(11, int(character.hp_current))
        self.assertNotIn("Rope", list(character.inventory))
        updated_world = world_repo.load_default()
        self.assertEqual(0, int(getattr(updated_world, "threat_level", 0) or 0))

    def test_no_combat_fallback_torch_counter_reduces_hp_and_threat(self) -> None:
        world_repo = InMemoryWorldRepository(seed=35)
        world = world_repo.load_default()
        world.threat_level = 1
        world_repo.save(world)

        character = Character(id=73, name="Ari", location_id=1, hp_current=12, hp_max=24)
        character.inventory = ["Torch"]
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Road")}),
            world_repo=world_repo,
        )

        with mock.patch("random.Random.randint", return_value=50):
            message = service._apply_explore_no_combat_fallback(character, [Entity(id=2, name="Raider", level=1)])

        self.assertIn("torchlight", message.lower())
        self.assertEqual(11, int(character.hp_current))
        self.assertNotIn("Torch", list(character.inventory))
        updated_world = world_repo.load_default()
        self.assertEqual(1, int(getattr(updated_world, "threat_level", 0) or 0))

    def test_no_combat_fallback_antitoxin_counter_cancels_threat_rise(self) -> None:
        world_repo = InMemoryWorldRepository(seed=36)
        world = world_repo.load_default()
        world.threat_level = 2
        world_repo.save(world)

        character = Character(id=74, name="Ari", location_id=1, hp_current=12, hp_max=24)
        character.inventory = ["Antitoxin"]
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Road")}),
            world_repo=world_repo,
        )

        with mock.patch("random.Random.randint", return_value=90):
            message = service._apply_explore_no_combat_fallback(character, [Entity(id=3, name="Skirmisher", level=1)])

        self.assertIn("antitoxin", message.lower())
        self.assertNotIn("Antitoxin", list(character.inventory))
        updated_world = world_repo.load_default()
        self.assertEqual(2, int(getattr(updated_world, "threat_level", 0) or 0))

    def test_social_success_can_advance_companion_arc(self) -> None:
        world_repo = InMemoryWorldRepository(seed=37)
        character = Character(id=75, name="Ari", location_id=1)
        character.attributes["charisma"] = 18
        character.flags = {
            "unlocked_companions": ["npc_silas", "npc_vael"],
            "companion_arcs": {
                "npc_vael": {"progress": 10, "trust": 10, "stage": "intro"},
            },
        }
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )

        with mock.patch("random.Random.randint", return_value=20):
            outcome = service.submit_social_approach_intent(character.id, "innkeeper_mara", "Friendly")

        self.assertTrue(outcome.success)
        saved = character_repo.get(character.id)
        self.assertIsNotNone(saved)
        arc = dict(saved.flags.get("companion_arcs", {})).get("npc_vael", {})
        self.assertGreater(int(dict(arc).get("progress", 0) or 0), 10)
        self.assertTrue(any("bond" in line.lower() for line in outcome.messages))

    def test_companion_leads_intent_includes_arc_progress_section(self) -> None:
        world_repo = InMemoryWorldRepository(seed=38)
        character = Character(id=76, name="Ari", location_id=1)
        character.flags = {
            "unlocked_companions": ["npc_silas", "npc_vael"],
            "companion_arcs": {
                "npc_vael": {"progress": 22, "trust": 11, "stage": "warming"},
            },
        }
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )

        lines = service.get_companion_leads_intent(character.id)
        joined = "\n".join(lines)
        self.assertIn("Arc Progress:", joined)
        self.assertIn("Vael: Arc 22/100", joined)

    def test_companion_arc_choice_available_when_bonded_and_unresolved(self) -> None:
        world_repo = InMemoryWorldRepository(seed=39)
        character = Character(id=77, name="Ari", location_id=1)
        character.flags = {
            "unlocked_companions": ["npc_silas", "npc_vael"],
            "companion_arcs": {
                "npc_vael": {"progress": 100, "trust": 32, "stage": "bonded"},
            },
        }
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )

        choices = service.get_companion_arc_choices_intent(character.id)

        self.assertTrue(any(companion_id == "npc_vael" for companion_id, _name in choices))

    def test_companion_arc_choice_locks_in_and_blocks_repeat(self) -> None:
        world_repo = InMemoryWorldRepository(seed=40)
        character = Character(id=78, name="Ari", location_id=1)
        character.flags = {
            "unlocked_companions": ["npc_silas", "npc_vael"],
            "companion_arcs": {
                "npc_vael": {"progress": 100, "trust": 30, "stage": "bonded"},
            },
        }
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )

        first = service.submit_companion_arc_choice_intent(character.id, "npc_vael", "oath")
        second = service.submit_companion_arc_choice_intent(character.id, "npc_vael", "distance")

        self.assertTrue(any("locked" in line.lower() for line in first.messages))
        self.assertTrue(any("no unresolved" in line.lower() for line in second.messages))
        saved = character_repo.get(character.id)
        self.assertIsNotNone(saved)
        outcomes = dict(saved.flags.get("companion_arc_outcomes", {}))
        self.assertEqual("oath", outcomes.get("npc_vael"))

    def test_game_loop_view_includes_time_and_weather_labels(self) -> None:
        world_repo = InMemoryWorldRepository(seed=41)
        world = world_repo.load_default()
        world.current_turn = 31
        world.threat_level = 2
        world_repo.save(world)

        character = Character(id=79, name="Ari", location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )

        view = service.get_game_loop_view(character.id)

        self.assertTrue(str(view.time_label).startswith("Day "))
        self.assertTrue(bool(str(view.weather_label).strip()))

    def test_camp_activity_requires_rations(self) -> None:
        world_repo = InMemoryWorldRepository(seed=42)
        character = Character(id=80, name="Ari", location_id=1, hp_current=7, hp_max=20)
        character.inventory = []
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Old Road", biome="forest")}),
            world_repo=world_repo,
        )

        result = service.submit_camp_activity_intent(character.id, "watch")

        self.assertTrue(any("rations" in line.lower() for line in result.messages))

    def test_camp_activity_consumes_rations_and_heals(self) -> None:
        world_repo = InMemoryWorldRepository(seed=43)
        character = Character(id=81, name="Ari", location_id=1, hp_current=6, hp_max=20)
        character.inventory = ["Sturdy Rations"]
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Deep Wild", biome="forest")}),
            world_repo=world_repo,
        )

        result = service.submit_camp_activity_intent(character.id, "watch")

        saved = character_repo.get(character.id)
        self.assertIsNotNone(saved)
        self.assertNotIn("Sturdy Rations", list(saved.inventory))
        self.assertGreaterEqual(int(saved.hp_current), 6)
        self.assertTrue(any("campfire" in line.lower() for line in result.messages))

    def test_rest_and_camp_surface_cataclysm_corruption_penalties(self) -> None:
        world_repo = InMemoryWorldRepository(seed=144)
        world = world_repo.load_default()
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "plague",
            "phase": "map_shrinks",
            "progress": 72,
            "seed": 456,
            "started_turn": 6,
            "last_advance_turn": world.current_turn,
        }
        world_repo.save(world)

        rest_character = Character(id=182, name="Ari", location_id=1, hp_current=8, hp_max=20)
        camp_character = Character(id=183, name="Ari", location_id=1, hp_current=8, hp_max=20)
        camp_character.inventory = ["Sturdy Rations"]

        rest_service = self._build_service(
            character_repo=InMemoryCharacterRepository({rest_character.id: rest_character}),
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )
        camp_service = self._build_service(
            character_repo=InMemoryCharacterRepository({camp_character.id: camp_character}),
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Deep Wild", biome="forest")}),
            world_repo=InMemoryWorldRepository(seed=144),
        )
        camp_world = camp_service.world_repo.load_default()
        camp_world.flags["cataclysm_state"] = dict(world.flags["cataclysm_state"])
        camp_service.world_repo.save(camp_world)

        rest_result = rest_service.rest_intent(rest_character.id)
        camp_result = camp_service.submit_camp_activity_intent(camp_character.id, "watch")

        self.assertTrue(any("corruption" in line.lower() for line in rest_result.messages))
        self.assertTrue(any("corruption" in line.lower() for line in camp_result.messages))

    def test_shop_after_hours_label_applies_at_night(self) -> None:
        world_repo = InMemoryWorldRepository(seed=44)
        world = world_repo.load_default()
        world.current_turn = 22
        world_repo.save(world)

        character = Character(id=82, name="Ari", location_id=1, money=100)
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )

        shop = service.get_shop_view_intent(character.id)

        self.assertIn("after-hours", str(shop.price_modifier_label).lower())

    def test_cataclysm_pressure_affects_shop_inventory_and_routes(self) -> None:
        world_repo = InMemoryWorldRepository(seed=188)
        world = world_repo.load_default()
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "demon_king",
            "phase": "ruin",
            "progress": 100,
            "seed": 999,
            "started_turn": 2,
            "last_advance_turn": world.current_turn,
        }
        world_repo.save(world)

        character = Character(id=190, name="Ari", location_id=1, money=200)
        character_repo = InMemoryCharacterRepository({character.id: character})
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Town", x=0.0, y=0.0),
                2: Location(id=2, name="Far Wild", biome="forest", x=0.0, y=0.0),
            }
        )
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=location_repo,
            world_repo=world_repo,
        )

        shop = service.get_shop_view_intent(character.id)
        destinations = service.get_travel_destinations_intent(character.id)

        item_ids = {item.item_id for item in shop.items}
        self.assertIn("cataclysm strain", str(shop.price_modifier_label).lower())
        self.assertNotIn("climbing_kit", item_ids)
        self.assertGreaterEqual(len(destinations), 1)
        self.assertTrue(any("cataclysm pressure" in destination.route_note.lower() for destination in destinations))

    def test_short_rest_recovers_less_than_long_rest(self) -> None:
        world_repo = InMemoryWorldRepository(seed=47)
        short_character = Character(id=86, name="Ari", location_id=1, hp_current=4, hp_max=20)
        short_character.spell_slots_max = 3
        short_character.spell_slots_current = 0
        long_character = Character(id=87, name="Ari", location_id=1, hp_current=4, hp_max=20)
        long_character.spell_slots_max = 3
        long_character.spell_slots_current = 0

        short_repo = InMemoryCharacterRepository({short_character.id: short_character})
        long_repo = InMemoryCharacterRepository({long_character.id: long_character})

        short_service = self._build_service(
            character_repo=short_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=world_repo,
        )
        long_service = self._build_service(
            character_repo=long_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Town")}),
            world_repo=InMemoryWorldRepository(seed=47),
        )

        short_service.short_rest_intent(short_character.id)
        long_service.long_rest_intent(long_character.id)

        saved_short = short_repo.get(short_character.id)
        saved_long = long_repo.get(long_character.id)
        self.assertIsNotNone(saved_short)
        self.assertIsNotNone(saved_long)
        self.assertLess(int(saved_short.hp_current), int(saved_long.hp_current))
        self.assertLess(int(saved_short.spell_slots_current), int(saved_long.spell_slots_current))

    def test_codex_bestiary_tier_progresses_unknown_to_known(self) -> None:
        world_repo = InMemoryWorldRepository(seed=48)
        character = Character(id=88, name="Ari", location_id=1, xp=0, money=0)
        character_repo = InMemoryCharacterRepository({character.id: character})
        monster = Entity(id=89, name="Grave Hound", level=3, faction_id="undead", armour_class=13, hp_max=18)
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([monster]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Crypt")}),
            world_repo=world_repo,
        )

        service.apply_encounter_reward_intent(character, monster)
        lines_after_first = service.get_codex_entries_intent(character.id)
        service.apply_encounter_reward_intent(character, monster)
        service.apply_encounter_reward_intent(character, monster)
        lines_after_third = service.get_codex_entries_intent(character.id)

        self.assertTrue(any("Unknown" in line and "Grave Hound" in line for line in lines_after_first))
        self.assertTrue(any("Known" in line and "Grave Hound" in line for line in lines_after_third))

    def test_encounter_reward_updates_bestiary_codex_entry(self) -> None:
        world_repo = InMemoryWorldRepository(seed=45)
        character = Character(id=83, name="Ari", location_id=1, xp=0, money=0)
        character_repo = InMemoryCharacterRepository({character.id: character})
        monster = Entity(id=84, name="Bog Wretch", level=2, faction_id="wild")
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([monster]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Mire")}),
            world_repo=world_repo,
        )

        service.apply_encounter_reward_intent(character, monster)
        service.apply_encounter_reward_intent(character, monster)

        saved = character_repo.get(character.id)
        self.assertIsNotNone(saved)
        codex = dict(saved.flags.get("codex_entries", {}))
        entry = dict(codex.get("bestiary:bog_wretch", {}))
        self.assertEqual("Bestiary", str(entry.get("category", "")))
        self.assertGreaterEqual(int(entry.get("discoveries", 0) or 0), 2)

    def test_investigate_wilderness_action_adds_lore_codex_entry(self) -> None:
        world_repo = InMemoryWorldRepository(seed=46)
        character = Character(id=85, name="Ari", location_id=1)
        character.attributes["intelligence"] = 18
        character_repo = InMemoryCharacterRepository({character.id: character})
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Ruins", biome="forest", factions=["wardens"])}),
            world_repo=world_repo,
        )

        with mock.patch("random.Random.randint", return_value=20):
            service.wilderness_action_intent(character.id, "investigate")

        saved = character_repo.get(character.id)
        self.assertIsNotNone(saved)
        codex = dict(saved.flags.get("codex_entries", {}))
        self.assertTrue(any(str(key).startswith("lore:investigate:") for key in codex.keys()))
        lore_entry = next((dict(value) for key, value in codex.items() if str(key).startswith("lore:investigate:")), {})
        self.assertIn("forest", str(lore_entry.get("body", "")).lower())
        self.assertIn("wardens", str(lore_entry.get("body", "")).lower())

    def test_encounter_intro_codex_hint_progression_unknown_observed_known(self) -> None:
        world_repo = InMemoryWorldRepository(seed=52)
        character = Character(id=90, name="Ari", location_id=1, xp=0, money=0)
        character_repo = InMemoryCharacterRepository({character.id: character})
        monster = Entity(id=91, name="Bog Wretch", level=2, faction_id="wild", armour_class=12)
        service = self._build_service(
            character_repo=character_repo,
            entity_repo=InMemoryEntityRepository([monster]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Mire")}),
            world_repo=world_repo,
        )

        first_intro = service.encounter_intro_intent(monster, character_id=character.id)
        self.assertIn("Unknown", first_intro)

        service.apply_encounter_reward_intent(character, monster)
        second_intro = service.encounter_intro_intent(monster, character_id=character.id)
        self.assertIn("Unknown", second_intro)

        service.apply_encounter_reward_intent(character, monster)
        third_intro = service.encounter_intro_intent(monster, character_id=character.id)
        self.assertIn("Observed", third_intro)

        service.apply_encounter_reward_intent(character, monster)
        fourth_intro = service.encounter_intro_intent(monster, character_id=character.id)
        self.assertIn("Known", fourth_intro)


if __name__ == "__main__":
    unittest.main()
