import io
import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.presentation import cli
from rpg.presentation.game_loop import _run_explore, _render_character_sheet, _run_rumour_board, _run_town, run_game_loop
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

        with mock.patch("rpg.presentation.game_loop._CONSOLE", None), mock.patch(
            "rpg.presentation.game_loop.arrow_menu", return_value=0
        ), mock.patch("builtins.input", return_value=""), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
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

        with mock.patch("rpg.presentation.game_loop._CONSOLE", None), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
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
        self.assertIsNotNone(character)
        if character is None:
            return
        character.money = 30
        game.character_repo.save(character)

        state = {"town": 0, "prep": 0}

        def _choose_menu(title, options):
            if str(title).startswith("Town Options"):
                if state["town"] == 0:
                    state["town"] += 1
                    return 5
                return 8
            if str(title).startswith("Travel Prep"):
                if state["prep"] == 0:
                    state["prep"] += 1
                    return 0
                return len(options) - 1
            return -1

        with mock.patch("rpg.presentation.game_loop._CONSOLE", None), mock.patch(
            "rpg.presentation.game_loop.arrow_menu",
            side_effect=_choose_menu,
        ), mock.patch("builtins.input", return_value=""), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            _run_town(game, character_id)

        transcript = output.getvalue()
        self.assertIn("TRAVEL PREP RESULT", transcript)
        self.assertIn("Travel prep secured", transcript)

    def test_town_talk_flow_uses_dialogue_session_loop(self) -> None:
        game, creation_service = cli._bootstrap_inmemory()

        with mock.patch("builtins.input", side_effect=["Asha", "2"]), mock.patch("sys.stdout", new_callable=io.StringIO):
            character_id = cli.run_character_creator(creation_service)

        state = {"town": 0, "dialogue": 0}

        def _choose_menu(title, options):
            if str(title).startswith("Town Options"):
                if state["town"] == 0:
                    state["town"] += 1
                    return 0
                return 8
            if str(title) == "Talk To Who?":
                return 0
            if str(title) == "Choose Dialogue":
                if state["dialogue"] == 0:
                    state["dialogue"] += 1
                    return 0
                return len(options) - 1
            return -1

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False), mock.patch(
            "rpg.presentation.game_loop._CONSOLE", None
        ), mock.patch(
            "rpg.presentation.game_loop.arrow_menu",
            side_effect=_choose_menu,
        ), mock.patch("builtins.input", return_value=""), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            _run_town(game, character_id)

        transcript = output.getvalue()
        self.assertIn("Social Outcome", transcript)
        self.assertIn("Relationship", transcript)

    def test_loop_header_shows_persistent_doomsday_warning_when_cataclysm_active(self) -> None:
        game, creation_service = cli._bootstrap_inmemory()
        with mock.patch("builtins.input", side_effect=["Asha", "2"]), mock.patch("sys.stdout", new_callable=io.StringIO):
            character_id = cli.run_character_creator(creation_service)

        self.assertIsNotNone(game.world_repo)
        if game.world_repo is None:
            return
        world = game.world_repo.load_default()
        self.assertIsNotNone(world)
        if world is None:
            return
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "plague",
            "phase": "grip_tightens",
            "progress": 42,
            "seed": 101,
            "started_turn": 3,
            "last_advance_turn": world.current_turn,
        }
        game.world_repo.save(world)

        with mock.patch("rpg.presentation.game_loop._CONSOLE", None), mock.patch(
            "rpg.presentation.game_loop.arrow_menu", return_value=4
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            run_game_loop(game, character_id)

        transcript = output.getvalue()
        self.assertIn("DOOMSDAY", transcript)
        self.assertIn("Grip Tightens", transcript)

    def test_rumour_board_surfaces_cataclysm_phase_bulletin(self) -> None:
        game, creation_service = cli._bootstrap_inmemory()
        with mock.patch("builtins.input", side_effect=["Asha", "2"]), mock.patch("sys.stdout", new_callable=io.StringIO):
            character_id = cli.run_character_creator(creation_service)

        self.assertIsNotNone(game.world_repo)
        if game.world_repo is None:
            return
        world = game.world_repo.load_default()
        self.assertIsNotNone(world)
        if world is None:
            return
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "demon_king",
            "phase": "map_shrinks",
            "progress": 67,
            "seed": 202,
            "started_turn": 2,
            "last_advance_turn": world.current_turn,
        }
        game.world_repo.save(world)

        with mock.patch("rpg.presentation.game_loop._CONSOLE", None), mock.patch("builtins.input", return_value=""), mock.patch(
            "sys.stdout", new_callable=io.StringIO
        ) as output:
            _run_rumour_board(game, character_id)

        transcript = output.getvalue()
        self.assertIn("Doomsday Bulletin", transcript)
        self.assertIn("Map Shrinks", transcript)

    def test_scripted_cli_loop_records_travel_hop_and_turn_advance(self) -> None:
        game, creation_service = cli._bootstrap_inmemory()

        with mock.patch("builtins.input", side_effect=["Phase25Hero", "2"]), mock.patch("sys.stdout", new_callable=io.StringIO):
            character_id = cli.run_character_creator(creation_service)

        world_before = game.world_repo.load_default() if game.world_repo is not None else None
        self.assertIsNotNone(world_before)
        if world_before is None:
            return
        start_turn = int(world_before.current_turn)

        state = {
            "root_actions": 0,
            "quest_board_visits": 0,
            "quest_accepts": 0,
            "wilderness_actions": 0,
            "travel_actions": 0,
            "travel_hops": 0,
        }

        def _choose_menu(title, options):
            text = str(title)
            if text.endswith("— Actions"):
                sequence = [0, 1, 0, 2, 4]
                idx = sequence[state["root_actions"]] if state["root_actions"] < len(sequence) else 4
                state["root_actions"] += 1
                if idx == 1:
                    state["travel_actions"] += 1
                return idx

            if text.startswith("Town Options"):
                if state["quest_board_visits"] == 0:
                    return 1
                return 8

            if text.startswith("Quest Board"):
                state["quest_board_visits"] += 1
                if state["quest_accepts"] == 0 and len(options) > 1:
                    state["quest_accepts"] += 1
                    return 0
                return len(options) - 1

            if text.startswith("Travel Mode"):
                return 0

            if text.startswith("Travel Pace"):
                return 1

            if "Wilderness Actions" in text:
                state["wilderness_actions"] += 1
                return 5

            if text.startswith("Wilderness Rest"):
                return 1

            if text in {"Leave Town", "Return to Town"}:
                if len(options) > 1:
                    state["travel_hops"] += 1
                    return 0
                return len(options) - 1 if options else -1

            return len(options) - 1 if options else -1

        with mock.patch("rpg.presentation.game_loop._CONSOLE", None), mock.patch(
            "rpg.presentation.game_loop.arrow_menu", side_effect=_choose_menu
        ), mock.patch("rpg.presentation.game_loop.clear_screen", lambda: None), mock.patch(
            "rpg.presentation.game_loop._prompt_continue", lambda *args, **kwargs: None
        ), mock.patch("builtins.input", return_value=""), mock.patch("sys.stdout", new_callable=io.StringIO):
            run_game_loop(game, character_id)

        world_after = game.world_repo.load_default() if game.world_repo is not None else None
        self.assertIsNotNone(world_after)
        if world_after is None:
            return

        self.assertGreaterEqual(state["travel_actions"], 1)
        self.assertGreater(int(world_after.current_turn), int(start_turn))


if __name__ == "__main__":
    unittest.main()
