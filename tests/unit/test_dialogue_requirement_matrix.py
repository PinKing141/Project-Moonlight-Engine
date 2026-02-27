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


if __name__ == "__main__":
    unittest.main()
