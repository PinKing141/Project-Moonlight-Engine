import io
import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.presentation import cli
from rpg.presentation.game_loop import _run_explore, _render_character_sheet, _run_town
from rpg.application.dtos import ExploreView


class CliFlowTests(unittest.TestCase):
    def test_character_creation_and_quit_flow(self) -> None:
        game, creation_service = cli._bootstrap_inmemory()

        with mock.patch("builtins.input", side_effect=["Asha", "2"]), mock.patch("sys.stdout", new_callable=io.StringIO):
            character_id = cli.run_character_creator(creation_service)

        characters = game.list_characters()
        self.assertTrue(any(char.id == character_id for char in characters))

        with mock.patch("builtins.input", side_effect=["quit"]), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            cli._run_game_loop(game, character_id)

        transcript = output.getvalue()
        self.assertIn("Turn", transcript)
        self.assertIn("Goodbye.", transcript)

    def test_explore_flow_uses_structured_message_without_readiness_placeholders(self) -> None:
        class StubService:
            @staticmethod
            def explore_intent(_character_id):
                return ExploreView(has_encounter=False, message="You mark hostile movement and avoid direct combat; local danger rises.", enemies=[]), None, []

        with mock.patch("builtins.input", return_value=""), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            _run_explore(StubService(), 1)

        transcript = output.getvalue()
        self.assertIn("avoid direct combat", transcript)
        self.assertNotIn("encounters coming later", transcript)
        self.assertNotIn("combat system is not ready yet", transcript)

    def test_character_sheet_render_includes_xp_progress(self) -> None:
        class StubSheet:
            name = "Asha"
            race = "Human"
            class_name = "fighter"
            level = 2
            xp = 42
            next_level_xp = 50
            xp_to_next_level = 8
            hp_current = 12
            hp_max = 18
            difficulty = "normal"

        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            _render_character_sheet(StubSheet())

        transcript = output.getvalue()
        self.assertIn("Level", transcript)
        self.assertIn("2", transcript)
        self.assertIn("42/50", transcript)
        self.assertIn("8", transcript)

    def test_town_travel_prep_flow_prints_purchase_result(self) -> None:
        game, creation_service = cli._bootstrap_inmemory()

        with mock.patch("builtins.input", side_effect=["Asha", "2"]), mock.patch("sys.stdout", new_callable=io.StringIO):
            character_id = cli.run_character_creator(creation_service)

        character = game.character_repo.get(character_id)
        character.money = 30
        game.character_repo.save(character)

        with mock.patch(
            "rpg.presentation.game_loop.arrow_menu",
            side_effect=[5, 0, 3, 7],
        ), mock.patch("builtins.input", return_value=""), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            _run_town(game, character_id)

        transcript = output.getvalue()
        self.assertIn("TRAVEL PREP RESULT", transcript)
        self.assertIn("Travel prep secured", transcript)


if __name__ == "__main__":
    unittest.main()
