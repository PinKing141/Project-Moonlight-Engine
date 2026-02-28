import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.dialogue_service import DialogueService
from rpg.domain.models.character import Character
from rpg.domain.models.world import World


class DialogueRequirementMatrixTests(unittest.TestCase):
    def _build_world_character(self):
        world = World(id=1, name="TestWorld", current_turn=12, rng_seed=77)
        world.flags.setdefault("narrative", {})
        character = Character(id=99, name="Iris", money=12)
        character.flags.setdefault("faction_heat", {})
        return world, character

    def test_tension_requirements_matrix(self) -> None:
        service = DialogueService()
        world, character = self._build_world_character()

        world.flags["narrative"]["tension_level"] = 20
        self.assertEqual(
            [],
            service._failed_requirements(
                world=world,
                character=character,
                character_id=99,
                npc_id="innkeeper_mara",
                required=["tension_low"],
            ),
        )
        self.assertEqual(
            ["tension_high"],
            service._failed_requirements(
                world=world,
                character=character,
                character_id=99,
                npc_id="innkeeper_mara",
                required=["tension_high"],
            ),
        )

        world.flags["narrative"]["tension_level"] = 85
        self.assertEqual(
            [],
            service._failed_requirements(
                world=world,
                character=character,
                character_id=99,
                npc_id="innkeeper_mara",
                required=["tension_high", "tension_critical"],
            ),
        )

    def test_faction_heat_high_requirement_matrix(self) -> None:
        service = DialogueService()
        world, character = self._build_world_character()

        character.flags["faction_heat"] = {"wardens": 9}
        self.assertEqual(
            ["faction_heat_wardens_high"],
            service._failed_requirements(
                world=world,
                character=character,
                character_id=99,
                npc_id="captain_ren",
                required=["faction_heat_wardens_high"],
            ),
        )

        character.flags["faction_heat"] = {"wardens": 12}
        self.assertEqual(
            [],
            service._failed_requirements(
                world=world,
                character=character,
                character_id=99,
                npc_id="captain_ren",
                required=["faction_heat_wardens_high"],
            ),
        )

    def test_dominant_faction_requirement_matrix(self) -> None:
        service = DialogueService()
        world, character = self._build_world_character()

        character.flags["faction_heat"] = {"wardens": 11, "the_crown": 8}
        self.assertEqual(
            ["dominant_faction_the_crown"],
            service._failed_requirements(
                world=world,
                character=character,
                character_id=99,
                npc_id="innkeeper_mara",
                required=["dominant_faction_the_crown"],
            ),
        )

        character.flags["faction_heat"] = {"wardens": 7, "the_crown": 12}
        self.assertEqual(
            [],
            service._failed_requirements(
                world=world,
                character=character,
                character_id=99,
                npc_id="innkeeper_mara",
                required=["dominant_faction_the_crown"],
            ),
        )

    def test_alignment_requirement_matrix(self) -> None:
        service = DialogueService()
        world, character = self._build_world_character()

        character.alignment = "true_neutral"
        self.assertEqual(
            ["alignment_lawful"],
            service._failed_requirements(
                world=world,
                character=character,
                character_id=99,
                npc_id="captain_ren",
                required=["alignment_lawful"],
            ),
        )

        character.alignment = "lawful_good"
        self.assertEqual(
            [],
            service._failed_requirements(
                world=world,
                character=character,
                character_id=99,
                npc_id="captain_ren",
                required=["alignment_lawful", "alignment_good"],
            ),
        )

    def test_template_authority_invoke_faction_is_alignment_gated(self) -> None:
        service = DialogueService()
        world, character = self._build_world_character()
        service._session_row(character=character, npc_id="generated_guard")["stage_id"] = "probe"

        character.alignment = "true_neutral"
        neutral_session = service.build_dialogue_session(
            world=world,
            character=character,
            character_id=99,
            npc_id="generated_guard",
            npc_name="Gate Warden",
            greeting="The warden waits.",
            approaches=["Direct", "Invoke Faction"],
            npc_profile_id="template:authority",
        )
        neutral_invoke = next(
            (row for row in neutral_session.get("choices", []) if str(row.get("choice_id", "")) == "invoke faction"),
            None,
        )
        self.assertIsNotNone(neutral_invoke)
        self.assertFalse(bool(neutral_invoke.get("available", False)))

        character.alignment = "lawful_neutral"
        lawful_session = service.build_dialogue_session(
            world=world,
            character=character,
            character_id=99,
            npc_id="generated_guard",
            npc_name="Gate Warden",
            greeting="The warden waits.",
            approaches=["Direct", "Invoke Faction"],
            npc_profile_id="template:authority",
        )
        lawful_invoke = next(
            (row for row in lawful_session.get("choices", []) if str(row.get("choice_id", "")) == "invoke faction"),
            None,
        )
        self.assertIsNotNone(lawful_invoke)
        self.assertTrue(bool(lawful_invoke.get("available", False)))

    def test_template_underworld_deception_is_alignment_gated(self) -> None:
        service = DialogueService()
        world, character = self._build_world_character()

        character.alignment = "lawful_good"
        blocked_session = service.build_dialogue_session(
            world=world,
            character=character,
            character_id=99,
            npc_id="generated_fixer",
            npc_name="Back-Alley Fixer",
            greeting="The fixer narrows their eyes.",
            approaches=["Friendly", "Direct"],
            npc_profile_id="template:underworld",
        )
        blocked_deceive = next(
            (row for row in blocked_session.get("choices", []) if str(row.get("choice_id", "")) == "deception check"),
            None,
        )
        self.assertIsNotNone(blocked_deceive)
        self.assertFalse(bool(blocked_deceive.get("available", False)))

        character.alignment = "chaotic_neutral"
        allowed_session = service.build_dialogue_session(
            world=world,
            character=character,
            character_id=99,
            npc_id="generated_fixer",
            npc_name="Back-Alley Fixer",
            greeting="The fixer narrows their eyes.",
            approaches=["Friendly", "Direct"],
            npc_profile_id="template:underworld",
        )
        allowed_deceive = next(
            (row for row in allowed_session.get("choices", []) if str(row.get("choice_id", "")) == "deception check"),
            None,
        )
        self.assertIsNotNone(allowed_deceive)
        self.assertTrue(bool(allowed_deceive.get("available", False)))


if __name__ == "__main__":
    unittest.main()
