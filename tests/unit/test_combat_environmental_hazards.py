import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.combat_service import CombatService
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity


class CombatEnvironmentalHazardsTests(unittest.TestCase):
    def test_spreading_fire_hazard_intensifies_and_logs(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(4)
        hero = Character(id=1, name="Rhea", class_name="fighter", hp_current=30, hp_max=30)
        enemy = Entity(id=2, name="Drake", level=4, hp=30, hp_current=30, hp_max=30, armour_class=10, damage_die="d4")
        scene = {"hazards": ["spreading_fire"]}
        log = []

        service._apply_round_lair_action(
            log=log,
            round_no=1,
            terrain="volcano",
            allies=[hero],
            enemies=[enemy],
            scene=scene,
        )
        service._apply_round_lair_action(
            log=log,
            round_no=2,
            terrain="volcano",
            allies=[hero],
            enemies=[enemy],
            scene=scene,
        )

        self.assertTrue(any("Spreading fire intensifies" in row.text for row in log))
        hazard_state = scene.get("_hazard_state", {})
        hazard_state_dict = hazard_state if isinstance(hazard_state, dict) else {}
        self.assertGreaterEqual(int(hazard_state_dict.get("fire_intensity", 0) or 0), 2)

    def test_trapline_hazard_can_restrain_targets(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(9)
        hero = Character(id=10, name="Ari", class_name="rogue", hp_current=28, hp_max=28)
        enemy = Entity(id=11, name="Bandit", level=2, hp=20, hp_current=20, hp_max=20, armour_class=10, damage_die="d4")
        scene = {"hazards": ["trapline"]}
        log = []

        service._apply_round_lair_action(
            log=log,
            round_no=1,
            terrain="cramped",
            allies=[hero],
            enemies=[enemy],
            scene=scene,
        )

        restrained_seen = service._has_status(hero, "restrained") or service._has_status(enemy, "restrained")
        self.assertTrue(restrained_seen or any("trap" in row.text.lower() for row in log))

    def test_boss_lair_action_triggers_on_initiative_twenty(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(12)

        hero = Character(id=21, name="Vale", class_name="fighter", hp_current=45, hp_max=45)
        hero.attributes["dexterity"] = 10
        boss = Entity(id=22, name="Ancient Tyrant", level=12, hp=120, hp_current=120, hp_max=120, armour_class=12, attack_bonus=0, damage_die="d4")

        def choose_action(_options, _player, _enemy, _round_no, _scene):
            return "Dodge"

        result = service.fight_turn_based(
            hero,
            boss,
            choose_action,
            scene={"distance": "close", "terrain": "open", "surprise": "none"},
        )

        self.assertTrue(any("Initiative 20 — Lair Action" in row.text for row in result.log))


if __name__ == "__main__":
    unittest.main()
