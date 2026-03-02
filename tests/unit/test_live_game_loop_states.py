import sys
from pathlib import Path
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.dtos import ExploreView
from rpg.presentation.live_game_loop import (
    CharacterSheetState,
    DialogueOverlayState,
    ExplorationState,
    InventoryState,
    LiveGameContext,
    RootState,
)


class _FakeGameService:
    def __init__(self) -> None:
        self.equip_calls: list[str] = []
        self.drop_calls: list[str] = []
        self.unequip_calls: list[str] = []
        self.swap_attune_calls: list[tuple[int, str, str]] = []
        self.world_spell_calls: list[tuple[int, str, int | None, bool]] = []
        self.dialogue_calls: list[tuple[int, str, str]] = []
        self._encounter = False
        self._location_type = "wilderness"
        self.character_repo = SimpleNamespace(
            get=lambda _character_id: SimpleNamespace(flags={"attuned_items": ["Moon Charm", "Sun Relic", "Storm Talisman"]})
        )

    def get_game_loop_view(self, character_id: int):
        _ = character_id
        return SimpleNamespace(
            name="Elara",
            race="human",
            class_name="fighter",
            hp_current=20,
            hp_max=20,
            world_turn=2,
            weather_label="Clear",
            time_label="Noon",
        )

    def get_location_context_intent(self, character_id: int):
        _ = character_id
        return SimpleNamespace(current_location_name="Ruined Courtyard", location_type=self._location_type)

    def get_town_view_intent(self, character_id: int):
        _ = character_id
        return SimpleNamespace(
            npcs=[
                SimpleNamespace(id="npc_kaelen", name="Kaelen", role="Captain", temperament="Stern", relationship=0),
                SimpleNamespace(id="npc_mirelle", name="Mirelle", role="Scholar", temperament="Curious", relationship=18),
            ]
        )

    def get_npc_interaction_intent(self, character_id: int, npc_id: str):
        _ = character_id
        return SimpleNamespace(
            npc_id=npc_id,
            npc_name="Kaelen" if npc_id == "npc_kaelen" else "Mirelle",
            role="Captain",
            temperament="Stern",
            relationship=0,
            greeting="State your business, traveler.",
            approaches=["Friendly", "Direct"],
        )

    def get_dialogue_session_intent(self, character_id: int, npc_id: str):
        _ = character_id
        _ = npc_id
        return SimpleNamespace(
            stage_id="opening",
            greeting="I've told you before. The gates stay shut at dusk.",
            challenge_progress=1,
            challenge_target=3,
            choices=[
                SimpleNamespace(choice_id="persuade", label="[Persuasion] I have urgent news.", available=True, locked_reason=""),
                SimpleNamespace(choice_id="leave", label="[Leave] Understood.", available=True, locked_reason=""),
            ],
        )

    def submit_dialogue_choice_intent(self, character_id: int, npc_id: str, choice_id: str):
        self.dialogue_calls.append((character_id, npc_id, choice_id))
        return SimpleNamespace(
            messages=["Kaelen narrows his eyes, then motions you through.", "Relationship: 0 → 2"],
            success=True,
            roll_total=14,
            target_dc=12,
        )

    def get_exploration_environment_intent(self, character_id: int):
        _ = character_id
        return {
            "light_level": "Dim",
            "detection_state": "Unaware",
            "detection_note": "Faint echoes from the north.",
        }

    def get_travel_destinations_intent(self, character_id: int):
        _ = character_id
        return [
            SimpleNamespace(name="North Archway"),
            SimpleNamespace(name="Collapsed Hall"),
            SimpleNamespace(name="Dune Path"),
        ]

    def short_rest_intent(self, character_id: int):
        _ = character_id
        return SimpleNamespace(messages=["You bind wounds and regain focus."])

    def list_spell_options(self, player):
        _ = player
        return [
            SimpleNamespace(slug="detect-magic", label="Detect Magic (Lv 1)", playable=True, cast_levels=[1], ritual=True),
        ]

    def cast_world_spell_intent(self, character_id: int, spell_slug: str, cast_level: int | None = None, as_ritual: bool = False):
        self.world_spell_calls.append((character_id, spell_slug, cast_level, as_ritual))
        if as_ritual:
            return SimpleNamespace(messages=["You complete the ritual casting of Detect Magic (+10 minutes)."])
        return SimpleNamespace(messages=["You cast Detect Magic."])

    def get_equipment_view_intent(self, character_id: int):
        _ = character_id
        return SimpleNamespace(
            equipped_slots={"weapon": "Rusty Sword", "armor": "Leather Armor", "trinket": "(empty)"},
            inventory_items=[
                SimpleNamespace(name="Rusty Sword", slot="weapon", equipable=True, equipped=True),
                SimpleNamespace(name="Dagger", slot="weapon", equipable=True, equipped=False),
                SimpleNamespace(name="Torch", slot=None, equipable=False, equipped=False),
            ],
        )

    def equip_inventory_item_intent(self, character_id: int, item_name: str):
        _ = character_id
        self.equip_calls.append(item_name)
        return SimpleNamespace(messages=[f"Equipped {item_name}."])

    def drop_inventory_item_intent(self, character_id: int, item_name: str):
        _ = character_id
        self.drop_calls.append(item_name)
        return SimpleNamespace(messages=[f"Dropped {item_name}."])

    def unequip_slot_intent(self, character_id: int, slot_name: str):
        _ = character_id
        self.unequip_calls.append(slot_name)
        return SimpleNamespace(messages=[f"Unequipped {slot_name}."])

    def swap_attuned_item_intent(self, character_id: int, old_item_name: str, new_item_name: str):
        self.swap_attune_calls.append((character_id, old_item_name, new_item_name))
        return SimpleNamespace(messages=[f"Attunement swapped: {old_item_name} -> {new_item_name}."])

    def explore_intent(self, character_id: int):
        _ = character_id
        if not self._encounter:
            return ExploreView(has_encounter=False, message="Quiet sands and distant wind.", enemies=[]), SimpleNamespace(), []

        enemy = SimpleNamespace(name="Goblin", hp_current=7, hp_max=7, id=77)
        player = SimpleNamespace(name="Elara", hp_current=20, hp_max=20, armour_class=16, id=42, flags={})
        return ExploreView(has_encounter=True, message="Hostiles rush from cover.", enemies=[]), player, [enemy]

    def consume_next_explore_surprise_intent(self, character_id: int):
        _ = character_id
        return None


class LiveGameLoopStateTests(unittest.TestCase):
    def test_root_routes_to_new_states(self) -> None:
        service = _FakeGameService()
        ctx = LiveGameContext(game_service=service, character_id=1)

        root = RootState()
        self.assertIsInstance(root.handle_input("1", ctx), ExplorationState)
        self.assertIsInstance(root.handle_input("e", ctx), ExplorationState)
        self.assertIsInstance(root.handle_input("4", ctx), InventoryState)
        self.assertIsInstance(root.handle_input("5", ctx), CharacterSheetState)

    def test_density_toggle_cycles_modes(self) -> None:
        service = _FakeGameService()
        ctx = LiveGameContext(game_service=service, character_id=1)
        root = RootState()

        root.handle_input("z", ctx)
        self.assertEqual("wide", str(ctx.ui_density))
        root.handle_input("z", ctx)
        self.assertEqual("compact", str(ctx.ui_density))
        root.handle_input("z", ctx)
        self.assertEqual("standard", str(ctx.ui_density))

    def test_exploration_dialogue_routes_to_overlay_in_town(self) -> None:
        service = _FakeGameService()
        service._location_type = "town"
        ctx = LiveGameContext(game_service=service, character_id=1)

        state = ExplorationState()
        next_state = state.handle_input("d", ctx)
        self.assertIsInstance(next_state, DialogueOverlayState)

    def test_exploration_explore_without_encounter_stays_in_exploration(self) -> None:
        service = _FakeGameService()
        ctx = LiveGameContext(game_service=service, character_id=1)

        state = ExplorationState()
        next_state = state.handle_input("e", ctx)
        self.assertIsInstance(next_state, ExplorationState)
        self.assertTrue(any("Quiet sands" in row for row in list(ctx.log_lines)))

    def test_exploration_explore_with_encounter_enters_combat_state(self) -> None:
        service = _FakeGameService()
        service._encounter = True
        ctx = LiveGameContext(game_service=service, character_id=1)

        state = ExplorationState()
        next_state = state.handle_input("e", ctx)
        self.assertEqual(type(next_state).__name__, "CombatState")

    def test_inventory_actions_call_service_intents(self) -> None:
        service = _FakeGameService()
        ctx = LiveGameContext(game_service=service, character_id=1)
        state = InventoryState()

        state.handle_input("e", ctx)
        state.handle_input("d", ctx)
        state.handle_input("u", ctx)

        self.assertIn("Rusty Sword", service.equip_calls)
        self.assertIn("Rusty Sword", service.drop_calls)
        self.assertIn("weapon", service.unequip_calls)

    def test_inventory_attunement_swap_calls_service_intent(self) -> None:
        service = _FakeGameService()
        ctx = LiveGameContext(game_service=service, character_id=1)
        state = InventoryState()

        state.handle_input("a", ctx)

        self.assertEqual(1, len(service.swap_attune_calls))
        character_id, old_item, new_item = service.swap_attune_calls[0]
        self.assertEqual(1, character_id)
        self.assertEqual("Moon Charm", old_item)
        self.assertEqual("Rusty Sword", new_item)

    def test_exploration_world_spellcast_calls_service_intent(self) -> None:
        service = _FakeGameService()
        ctx = LiveGameContext(game_service=service, character_id=1)
        state = ExplorationState()

        next_state = state.handle_input("m", ctx)

        self.assertIsInstance(next_state, ExplorationState)
        self.assertEqual(1, len(service.world_spell_calls))
        character_id, spell_slug, cast_level, as_ritual = service.world_spell_calls[0]
        self.assertEqual(1, character_id)
        self.assertEqual("detect-magic", spell_slug)
        self.assertEqual(1, cast_level)
        self.assertFalse(as_ritual)

    def test_dialogue_overlay_select_and_submit_choice(self) -> None:
        service = _FakeGameService()
        service._location_type = "town"
        ctx = LiveGameContext(game_service=service, character_id=1)
        state = DialogueOverlayState(return_state=ExplorationState())

        state = state.handle_input("1", ctx)
        self.assertIsInstance(state, DialogueOverlayState)
        state = state.handle_input("1", ctx)
        self.assertIsInstance(state, DialogueOverlayState)

        self.assertEqual(1, len(service.dialogue_calls))
        character_id, npc_id, choice_id = service.dialogue_calls[0]
        self.assertEqual(1, character_id)
        self.assertEqual("npc_kaelen", npc_id)
        self.assertEqual("persuade", choice_id)


if __name__ == "__main__":
    unittest.main()
