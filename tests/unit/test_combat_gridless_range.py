import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.combat_service import CombatService
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity


class CombatGridlessRangeTests(unittest.TestCase):
    def test_enemy_ai_prefers_hide_for_ambusher_in_cover(self) -> None:
        service = CombatService(verbosity="compact")
        hero = Character(id=201, name="Rin", class_name="fighter", hp_current=20, hp_max=20)
        enemy = Entity(id=202, name="Shade", kind="fiend", level=2, hp=18, hp_current=18, hp_max=18, armour_class=12, damage_die="d4")

        with mock.patch.object(service.rng, "randint", return_value=10):
            action = service._select_enemy_tactical_action(
                intent="ambusher",
                actor=enemy,
                target=hero,
                terrain="forest",
                distance="near",
                default_action="attack",
            )

        self.assertEqual("hide", action)

    def test_enemy_ai_prefers_grapple_for_brute_when_engaged(self) -> None:
        service = CombatService(verbosity="compact")
        hero = Character(id=211, name="Vera", class_name="fighter", hp_current=22, hp_max=22)
        enemy = Entity(id=212, name="Brute", kind="construct", level=2, hp=22, hp_current=22, hp_max=22, armour_class=12, damage_die="d4")

        with mock.patch.object(service.rng, "randint", return_value=15):
            action = service._select_enemy_tactical_action(
                intent="brute",
                actor=enemy,
                target=hero,
                terrain="open",
                distance="engaged",
                default_action="attack",
            )

        self.assertEqual("grapple", action)

    def test_enemy_ai_prefers_shove_for_cautious_when_engaged(self) -> None:
        service = CombatService(verbosity="compact")
        hero = Character(id=221, name="Ari", class_name="fighter", hp_current=22, hp_max=22)
        enemy = Entity(id=222, name="Skirmisher", kind="humanoid", level=2, hp=20, hp_current=20, hp_max=20, armour_class=12, damage_die="d4")

        with mock.patch.object(service.rng, "randint", return_value=20):
            action = service._select_enemy_tactical_action(
                intent="cautious",
                actor=enemy,
                target=hero,
                terrain="open",
                distance="engaged",
                default_action="attack",
            )

        self.assertEqual("shove", action)

    def test_enemy_ai_prefers_disengage_when_low_hp_and_threatened(self) -> None:
        service = CombatService(verbosity="compact")
        hero = Character(id=231, name="Ari", class_name="fighter", hp_current=22, hp_max=22)
        enemy = Entity(id=232, name="Scout", kind="humanoid", level=2, hp=20, hp_current=8, hp_max=20, armour_class=12, damage_die="d4")

        with mock.patch.object(service.rng, "randint", return_value=20):
            action = service._select_enemy_tactical_action(
                intent="cautious",
                actor=enemy,
                target=hero,
                terrain="open",
                distance="engaged",
                default_action="attack",
            )

        self.assertEqual("disengage", action)

    def test_enemy_ai_ranged_prefers_disengage_when_engaged(self) -> None:
        service = CombatService(verbosity="compact")
        hero = Character(id=236, name="Ari", class_name="fighter", hp_current=22, hp_max=22)
        enemy = Entity(id=237, name="Bandit Archer", kind="humanoid", level=2, hp=20, hp_current=20, hp_max=20, armour_class=12, damage_die="d4")

        with mock.patch.object(service.rng, "randint", return_value=20):
            action = service._select_enemy_tactical_action(
                intent="ambusher",
                actor=enemy,
                target=hero,
                terrain="forest",
                distance="engaged",
                default_action="attack",
            )

        self.assertEqual("disengage", action)

    def test_enemy_ai_ranged_aggressive_also_prefers_disengage_when_engaged(self) -> None:
        service = CombatService(verbosity="compact")
        hero = Character(id=238, name="Ari", class_name="fighter", hp_current=22, hp_max=22)
        enemy = Entity(id=239, name="Goblin Archer", kind="beast", level=2, hp=20, hp_current=20, hp_max=20, armour_class=12, damage_die="d4")

        with mock.patch.object(service.rng, "randint", return_value=90):
            action = service._select_enemy_tactical_action(
                intent="aggressive",
                actor=enemy,
                target=hero,
                terrain="open",
                distance="engaged",
                default_action="attack",
            )

        self.assertEqual("disengage", action)

    def test_enemy_disengage_action_repositions_distance(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(33)

        hero = Character(id=241, name="Bran", class_name="fighter", hp_current=24, hp_max=24)
        enemy = Entity(id=242, name="Skirmisher", kind="humanoid", level=2, hp=18, hp_current=8, hp_max=18, armour_class=12, damage_die="d4")

        def choose_action(_options, _player, _enemy, _round_no, _scene):
            return "Dodge"

        with mock.patch.object(service, "_select_enemy_action", return_value=("attack", None)), mock.patch.object(
            service.rng, "randint", return_value=20
        ):
            result = service.fight_turn_based(
                hero,
                enemy,
                choose_action,
                scene={"distance": "engaged", "terrain": "open", "surprise": "none"},
            )

        self.assertTrue(any("disengages to near" in row.text.lower() for row in result.log))

    def test_combat_options_include_tactical_utility_actions(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(13)

        hero = Character(id=31, name="Tamsin", class_name="fighter", hp_current=20, hp_max=20)
        enemy = Entity(id=32, name="Cutthroat", level=1, hp=16, hp_current=16, hp_max=16, armour_class=12, damage_die="d4")

        seen_options: list[str] = []

        def choose_action(options, _player, _enemy, _round_no, _scene):
            seen_options[:] = list(options)
            return "Flee" if "Flee" in options else options[0]

        service.fight_turn_based(
            hero,
            enemy,
            choose_action,
            scene={"distance": "engaged", "terrain": "open", "surprise": "none"},
        )

        for action_name in ("Disengage", "Hide", "Help", "Grapple", "Shove"):
            self.assertIn(action_name, seen_options)

    def test_melee_attack_not_viable_at_far_band(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(5)

        hero = Character(id=1, name="Bran", class_name="fighter", hp_current=20, hp_max=20)
        hero.attributes["strength"] = 14
        enemy = Entity(id=2, name="Raider", level=1, hp=14, hp_current=14, hp_max=14, armour_class=12, damage_die="d4")

        def choose_action(options, _player, _enemy, _round_no, _scene):
            return "Attack" if "Attack" in options else options[0]

        result = service.fight_turn_based(
            hero,
            enemy,
            choose_action,
            scene={"distance": "far", "terrain": "open", "surprise": "none"},
        )

        self.assertTrue(any("out of melee range" in row.text.lower() for row in result.log))

    def test_dash_closes_far_to_near_to_engaged(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(7)

        hero = Character(id=3, name="Kira", class_name="fighter", hp_current=20, hp_max=20)
        enemy = Entity(id=4, name="Bandit", level=1, hp=20, hp_current=20, hp_max=20, armour_class=12, damage_die="d4")

        turn = {"count": 0}

        def choose_action(options, _player, _enemy, _round_no, _scene):
            turn["count"] += 1
            if turn["count"] in {1, 2} and "Dash" in options:
                return "Dash"
            return "Flee" if "Flee" in options else options[0]

        result = service.fight_turn_based(
            hero,
            enemy,
            choose_action,
            scene={"distance": "far", "terrain": "open", "surprise": "none"},
        )

        self.assertTrue(any("distance is now near" in row.text.lower() for row in result.log))
        self.assertTrue(any("distance is now engaged" in row.text.lower() for row in result.log))

    def test_grapple_applies_grappled_state_and_logs(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(21)

        hero = Character(id=41, name="Marek", class_name="fighter", hp_current=24, hp_max=24)
        hero.attributes["strength"] = 16
        enemy = Entity(id=42, name="Raider", level=1, hp=22, hp_current=22, hp_max=22, armour_class=12, damage_die="d4", attack_bonus=1)

        turn = {"count": 0}

        def choose_action(options, _player, _enemy, _round_no, _scene):
            turn["count"] += 1
            if turn["count"] == 1 and "Grapple" in options:
                return "Grapple"
            return "Flee" if "Flee" in options else options[0]

        result = service.fight_turn_based(
            hero,
            enemy,
            choose_action,
            scene={"distance": "engaged", "terrain": "open", "surprise": "none"},
        )

        self.assertTrue(any("grapple" in row.text.lower() for row in result.log))


if __name__ == "__main__":
    unittest.main()
