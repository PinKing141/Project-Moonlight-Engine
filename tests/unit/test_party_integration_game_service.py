import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.application.services.combat_service import PartyCombatResult
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class PartyIntegrationGameServiceTests(unittest.TestCase):
    @staticmethod
    def _character_id(character: Character) -> int:
        character_id = character.id
        if character_id is None:
            raise AssertionError("Expected character.id to be assigned")
        return int(character_id)

    def _build_service(self, character: Character, faction_repo=None) -> GameService:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=101)
        character_repo = InMemoryCharacterRepository({self._character_id(character): character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Field")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        return GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
        )

    def test_active_party_companions_loaded_from_character_flags(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"active_party": ["npc_silas", "npc_elara"]}
        service = self._build_service(player)

        companions = service._active_party_companions(player)

        self.assertEqual(2, len(companions))
        names = {row.name for row in companions}
        self.assertIn("Silas", names)
        self.assertIn("Elara", names)

    def test_combat_resolve_party_intent_routes_through_party_engine(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"active_party": ["npc_silas"]}
        service = self._build_service(player)
        enemies = [Entity(id=99, name="Goblin", level=1, hp=8, hp_current=8, hp_max=8, armour_class=10)]

        captured = {"allies": 0, "enemies": 0}

        def fake_party_fight(*, allies, enemies, choose_action, choose_target, evaluate_ai_action, scene):
            captured["allies"] = len(allies)
            captured["enemies"] = len(enemies)
            return PartyCombatResult(allies=allies, enemies=enemies, log=[], allies_won=True, fled=False)

        with mock.patch.object(service.combat_service, "fight_party_turn_based", side_effect=fake_party_fight):
            result = service.combat_resolve_party_intent(
                player,
                enemies,
                choose_action=lambda options, p, e, round_no, ctx: "Attack",
                choose_target=lambda *args, **kwargs: 0,
                scene={"distance": "close", "terrain": "open", "surprise": "none"},
            )

        self.assertTrue(result.allies_won)
        self.assertEqual(2, captured["allies"])  # player + npc_silas
        self.assertEqual(1, captured["enemies"])

    def test_companion_runtime_state_persists_between_party_combats(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"active_party": ["npc_elara"]}
        service = self._build_service(player)
        enemies = [Entity(id=99, name="Goblin", level=1, hp=8, hp_current=8, hp_max=8, armour_class=10)]

        captured_inputs: list[tuple[int, int]] = []

        def fake_party_fight(*, allies, enemies, choose_action, choose_target, evaluate_ai_action, scene):
            _ = enemies
            _ = choose_action
            _ = choose_target
            _ = evaluate_ai_action
            _ = scene
            elara = next((row for row in allies if row.name == "Elara"), None)
            if elara is None:
                self.fail("Expected Elara in ally party")
            captured_inputs.append((int(elara.hp_current), int(elara.spell_slots_current)))

            elara.hp_current = max(0, int(elara.hp_current) - 3)
            elara.spell_slots_current = max(0, int(elara.spell_slots_current) - 1)
            return PartyCombatResult(allies=allies, enemies=[], log=[], allies_won=True, fled=False)

        with mock.patch.object(service.combat_service, "fight_party_turn_based", side_effect=fake_party_fight):
            service.combat_resolve_party_intent(
                player,
                enemies,
                choose_action=lambda options, p, e, round_no, ctx: "Attack",
                choose_target=lambda *args, **kwargs: 0,
                scene={"distance": "close", "terrain": "open", "surprise": "none"},
            )
            service.combat_resolve_party_intent(
                player,
                enemies,
                choose_action=lambda options, p, e, round_no, ctx: "Attack",
                choose_target=lambda *args, **kwargs: 0,
                scene={"distance": "close", "terrain": "open", "surprise": "none"},
            )

        self.assertEqual(2, len(captured_inputs))
        first_hp, first_slots = captured_inputs[0]
        second_hp, second_slots = captured_inputs[1]
        self.assertEqual(first_hp - 3, second_hp)
        self.assertEqual(first_slots - 1, second_slots)

    def test_rest_recovers_companion_runtime_hp_and_spell_slots(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {
            "active_party": ["npc_elara"],
            "party_runtime_state": {
                "npc_elara": {
                    "hp_current": 4,
                    "hp_max": 14,
                    "alive": True,
                    "spell_slots_current": 0,
                    "spell_slots_max": 2,
                }
            },
        }
        service = self._build_service(player)
        player_id = self._character_id(player)

        service.rest(player_id)

        saved = service.character_repo.get(player_id)
        if saved is None:
            self.fail("Expected saved player after rest")
        state = saved.flags.get("party_runtime_state", {}).get("npc_elara", {})
        self.assertEqual(10, state.get("hp_current"))
        self.assertEqual(1, state.get("spell_slots_current"))

    def test_travel_recovers_companion_runtime_hp_partially(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {
            "active_party": ["npc_silas"],
            "party_runtime_state": {
                "npc_silas": {
                    "hp_current": 8,
                    "hp_max": 16,
                    "alive": True,
                    "spell_slots_current": 0,
                    "spell_slots_max": 0,
                }
            },
        }
        player_id = self._character_id(player)

        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=101)
        character_repo = InMemoryCharacterRepository({player_id: player})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Town", biome="village", x=0.0, y=0.0),
                2: Location(id=2, name="Wilds", biome="forest", x=20.0, y=0.0),
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

        service.travel_intent(player_id, destination_id=2, travel_mode="road")

        saved = service.character_repo.get(player_id)
        if saved is None:
            self.fail("Expected saved player after travel")
        state = saved.flags.get("party_runtime_state", {}).get("npc_silas", {})
        self.assertEqual(10, state.get("hp_current"))

    def test_party_status_intent_reports_companion_hp_and_slots(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {
            "active_party": ["npc_silas", "npc_elara"],
            "party_runtime_state": {
                "npc_silas": {"hp_current": 9, "hp_max": 16, "alive": True, "spell_slots_current": 0, "spell_slots_max": 0},
                "npc_elara": {"hp_current": 11, "hp_max": 14, "alive": True, "spell_slots_current": 1, "spell_slots_max": 2},
            },
        }
        service = self._build_service(player)
        player_id = self._character_id(player)

        lines = service.get_party_status_intent(player_id)

        self.assertEqual(2, len(lines))
        self.assertTrue(any("Silas: HP 9/16" in line for line in lines))
        self.assertTrue(any("Elara: HP 11/14, Slots 1/2" in line for line in lines))

    def test_set_party_companion_active_adds_and_removes_member(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"unlocked_companions": ["npc_silas"]}
        service = self._build_service(player)
        player_id = self._character_id(player)

        add_result = service.set_party_companion_active_intent(player_id, "npc_silas", True)
        self.assertIn("joined", " ".join(add_result.messages).lower())

        saved = service.character_repo.get(player_id)
        if saved is None:
            self.fail("Expected saved player after adding companion")
        self.assertIn("npc_silas", saved.flags.get("active_party", []))

        remove_result = service.set_party_companion_active_intent(player_id, "npc_silas", False)
        self.assertIn("left", " ".join(remove_result.messages).lower())
        saved = service.character_repo.get(player_id)
        if saved is None:
            self.fail("Expected saved player after removing companion")
        self.assertNotIn("npc_silas", saved.flags.get("active_party", []))

    def test_set_party_companion_lane_override_applies_to_loaded_companion(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"active_party": ["npc_silas"]}
        service = self._build_service(player)
        player_id = self._character_id(player)

        lane_result = service.set_party_companion_lane_intent(player_id, "npc_silas", "rearguard")
        self.assertIn("rearguard", " ".join(lane_result.messages).lower())

        saved = service.character_repo.get(player_id)
        if saved is None:
            self.fail("Expected saved player after lane change")
        self.assertEqual("rearguard", saved.flags.get("party_lane_overrides", {}).get("npc_silas"))

        companions = service._active_party_companions(saved)
        self.assertEqual(1, len(companions))
        self.assertEqual("rearguard", companions[0].flags.get("combat_lane"))

    def test_set_party_companion_active_blocks_when_party_is_full(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {
            "active_party": ["npc_silas", "npc_elara", "captain_ren"],
            "unlocked_companions": ["npc_silas", "npc_elara", "captain_ren", "npc_lyra"],
        }
        service = self._build_service(player)
        player_id = self._character_id(player)

        templates = dict(service._COMPANION_TEMPLATES)
        templates["npc_lyra"] = {
            "name": "Lyra",
            "class_name": "cleric",
            "hp_max": 15,
            "attributes": {"wisdom": 15, "constitution": 12, "strength": 10, "dexterity": 10, "intelligence": 11, "charisma": 13},
            "known_spells": ["Cure Wounds"],
            "spell_slots_max": 2,
        }

        with mock.patch.object(service, "_COMPANION_TEMPLATES", templates):
            blocked = service.set_party_companion_active_intent(player_id, "npc_lyra", True)
            self.assertIn("party is full", " ".join(blocked.messages).lower())

            saved = service.character_repo.get(player_id)
            if saved is None:
                self.fail("Expected saved player while party remains full")
            self.assertNotIn("npc_lyra", saved.flags.get("active_party", []))

            active_count, cap = service.get_party_capacity_intent(player_id)
            self.assertEqual(3, active_count)
            self.assertEqual(3, cap)

    def test_recruit_companion_blocks_without_discovery_lead(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"unlocked_companions": ["npc_silas"]}
        service = self._build_service(player)
        player_id = self._character_id(player)

        result = service.recruit_companion_intent(player_id, "npc_vael")

        merged = " ".join(result.messages).lower()
        self.assertIn("not ready to join", merged)
        self.assertIn("no lead yet", merged)

    def test_recruit_companion_succeeds_after_discovery_lead(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"unlocked_companions": ["npc_silas"], "companion_leads": ["npc_vael"]}
        service = self._build_service(player)
        player_id = self._character_id(player)

        result = service.recruit_companion_intent(player_id, "npc_vael")
        self.assertIn("joins your roster", " ".join(result.messages).lower())

        saved = service.character_repo.get(player_id)
        if saved is None:
            self.fail("Expected saved player after recruit")
        self.assertIn("npc_vael", saved.flags.get("unlocked_companions", []))

    def test_recruit_companion_blocked_by_mutual_exclusive_rival(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"unlocked_companions": ["npc_silas", "npc_seraphine"], "companion_leads": ["npc_vael"]}
        service = self._build_service(player)
        player_id = self._character_id(player)

        result = service.recruit_companion_intent(player_id, "npc_vael")

        merged = " ".join(result.messages).lower()
        self.assertIn("not ready to join", merged)
        self.assertIn("refuses to join", merged)

    def test_recruit_companion_blocked_by_campaign_rare_cap(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {
            "unlocked_companions": ["npc_silas", "npc_elara", "captain_ren", "npc_vael", "npc_seraphine", "npc_kaelen"],
            "companion_leads": ["npc_mirelle"],
        }
        service = self._build_service(player)
        player_id = self._character_id(player)

        result = service.recruit_companion_intent(player_id, "npc_mirelle")

        merged = " ".join(result.messages).lower()
        self.assertIn("campaign recruit cap reached", merged)

    def test_activation_requires_companion_recruited(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"unlocked_companions": ["npc_silas"]}
        service = self._build_service(player)
        player_id = self._character_id(player)

        result = service.set_party_companion_active_intent(player_id, "npc_vael", True)

        self.assertIn("not recruited", " ".join(result.messages).lower())

    def test_npc_interaction_hides_ask_about_companions_option(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {}
        service = self._build_service(player)
        player_id = self._character_id(player)

        interaction = service.get_npc_interaction_intent(player_id, "broker_silas")

        approaches = {entry.lower() for entry in interaction.approaches}
        self.assertNotIn("ask about companions", approaches)

    def test_successful_social_interaction_unlocks_mapped_companion(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"unlocked_companions": []}
        service = self._build_service(player)
        player_id = self._character_id(player)

        with mock.patch("random.Random.randint", return_value=20):
            outcome = service.submit_social_approach_intent(player_id, "broker_silas", "friendly")

        self.assertIn("willing to join your roster", " ".join(outcome.messages).lower())
        saved = service.character_repo.get(player_id)
        if saved is None:
            self.fail("Expected saved player after social unlock")
        self.assertIn("npc_silas", set(saved.flags.get("unlocked_companions", [])))

    def test_companion_leads_intent_returns_empty_when_disabled(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {
            "unlocked_companions": ["npc_silas", "npc_elara", "captain_ren", "npc_vael"],
            "companion_leads": ["npc_seraphine"],
            "companion_lead_history": [
                {
                    "companion_id": "npc_seraphine",
                    "turn": 12,
                    "context": "rumour",
                    "location": "North Village",
                }
            ],
        }
        service = self._build_service(player)
        player_id = self._character_id(player)

        lines = service.get_companion_leads_intent(player_id)
        self.assertEqual([], lines)

    def test_recruit_companion_initializes_arc_state(self) -> None:
        player = Character(id=1, name="Ari", class_name="fighter", location_id=1)
        player.flags = {"unlocked_companions": ["npc_silas"], "companion_leads": ["npc_vael"]}
        service = self._build_service(player)
        player_id = self._character_id(player)

        service.recruit_companion_intent(player_id, "npc_vael")

        saved = service.character_repo.get(player_id)
        if saved is None:
            self.fail("Expected saved player after recruit")
        arcs = dict(saved.flags.get("companion_arcs", {}))
        self.assertIn("npc_vael", arcs)
        self.assertGreaterEqual(int(dict(arcs["npc_vael"]).get("progress", 0)), 5)


if __name__ == "__main__":
    unittest.main()
