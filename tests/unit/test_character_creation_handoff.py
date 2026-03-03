from types import SimpleNamespace
from unittest import TestCase, mock

from rpg.application.dtos import CharacterCreationSummaryView
from rpg.presentation import character_creation_ui as ui


class _StubCreationService:
    def __init__(self, *, character_id):
        self._character_id = character_id

    def list_classes(self):
        return [SimpleNamespace(name="Fighter", slug="fighter")]

    def list_class_names(self):
        return ["Fighter"]

    def create_character(self, **_kwargs):
        return SimpleNamespace(
            id=self._character_id,
            name="Asha",
            level=1,
            class_name="fighter",
            alignment="true_neutral",
            race="Human",
            speed=30,
            background="Acolyte",
            difficulty="normal",
            hp_current=10,
            hp_max=10,
            attributes={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
            race_traits=[],
            background_features=[],
            inventory=[],
            flags={},
        )


class _StubGameService:
    def __init__(self, creation_service, summary_id: int):
        self.character_creation_service = creation_service
        self._summary_id = int(summary_id)

    def build_character_creation_summary(self, _character):
        return CharacterCreationSummaryView(
            character_id=self._summary_id,
            name="Asha",
            level=1,
            class_name="Fighter",
            alignment="True Neutral",
            race="Human",
            speed=30,
            background="Acolyte",
            difficulty="Normal",
            hp_current=10,
            hp_max=10,
            attributes_line="STR 10 / DEX 10 / CON 10 / INT 10 / WIS 10 / CHA 10",
        )


class CharacterCreationHandoffTests(TestCase):
    def _patch_creation_steps(self):
        patches = [
            mock.patch.object(ui, "_choose_name", return_value=(True, "Asha")),
            mock.patch.object(ui, "_choose_race", return_value=SimpleNamespace(name="Human", playable=True, traits=[])),
            mock.patch.object(ui, "_choose_subrace", return_value=(True, None)),
            mock.patch.object(ui, "_choose_name_generation_gender", return_value="female"),
            mock.patch.object(ui, "_show_class_detail", return_value=True),
            mock.patch.object(ui, "_choose_equipment", return_value={"items": [], "gold_bonus": 0, "mode": "standard_equipment", "label": "Standard equipment"}),
            mock.patch.object(ui, "_choose_spells", return_value={"cantrips": [], "spells": []}),
            mock.patch.object(ui, "_choose_abilities", return_value={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}),
            mock.patch.object(ui, "_choose_background", return_value=SimpleNamespace(name="Acolyte")),
            mock.patch.object(ui, "_choose_background_extras", return_value={"tools": [], "languages": []}),
            mock.patch.object(ui, "_choose_personality_profile", return_value={}),
            mock.patch.object(ui, "_choose_level1_class_features", return_value={}),
            mock.patch.object(ui, "_choose_level1_feat", return_value=""),
            mock.patch.object(ui, "_choose_difficulty", return_value=SimpleNamespace(name="Normal")),
            mock.patch.object(ui, "_choose_alignment", return_value="true_neutral"),
            mock.patch.object(ui, "_render_character_summary", return_value=None),
            mock.patch.object(ui, "_prompt_enter", return_value=None),
        ]
        return patches

    def test_run_character_creation_falls_back_to_created_character_id_when_summary_id_missing(self) -> None:
        creation_service = _StubCreationService(character_id=7)
        game_service = _StubGameService(creation_service, summary_id=0)

        patches = self._patch_creation_steps()
        patches.append(mock.patch.object(ui, "_run_creation_skill_training_flow", return_value=None))

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12], patches[13], patches[14], patches[15], patches[16], patches[17]:
            character_id = ui.run_character_creation(game_service)

        self.assertEqual(7, character_id)

    def test_run_character_creation_returns_none_when_no_valid_character_id(self) -> None:
        creation_service = _StubCreationService(character_id=None)
        game_service = _StubGameService(creation_service, summary_id=0)

        patches = self._patch_creation_steps()
        patches.append(mock.patch.object(ui, "_run_creation_skill_training_flow", return_value=None))

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12], patches[13], patches[14], patches[15], patches[16], patches[17]:
            character_id = ui.run_character_creation(game_service)

        self.assertIsNone(character_id)

    def test_run_character_creation_continues_when_skill_training_step_fails(self) -> None:
        creation_service = _StubCreationService(character_id=9)
        game_service = _StubGameService(creation_service, summary_id=9)

        patches = self._patch_creation_steps()
        patches.append(mock.patch.object(ui, "_run_creation_skill_training_flow", side_effect=RuntimeError("boom")))

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12], patches[13], patches[14], patches[15], patches[16], patches[17]:
            character_id = ui.run_character_creation(game_service)

        self.assertEqual(9, character_id)
