import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.combat_service import CombatService
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity


class PartyInitiativeQueueTests(unittest.TestCase):
    def test_party_combat_logs_initiative_queue(self) -> None:
        service = CombatService(verbosity="normal")
        service.set_seed(17)

        allies = [
            Character(id=1, name="Ari", class_name="fighter", hp_current=18, hp_max=18),
            Character(id=2, name="Silas", class_name="rogue", hp_current=14, hp_max=14),
        ]
        allies[0].attributes["dexterity"] = 14
        allies[1].attributes["dexterity"] = 16

        enemies = [
            Entity(id=101, name="Goblin A", level=1, hp=8, hp_current=8, hp_max=8, armour_class=10, attack_bonus=1, damage_die="d4"),
            Entity(id=102, name="Goblin B", level=1, hp=8, hp_current=8, hp_max=8, armour_class=10, attack_bonus=1, damage_die="d4"),
        ]

        def choose_action(options, _player, _enemy, _round_no, _scene):
            return "Attack" if "Attack" in options else options[0]

        result = service.fight_party_turn_based(allies, enemies, choose_action)

        self.assertTrue(any("Initiative queue:" in row.text for row in result.log))
        self.assertTrue(any("Ari" in row.text for row in result.log))
        self.assertTrue(any("Goblin A" in row.text for row in result.log))

    def test_party_combat_resolves_until_one_side_falls(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(7)

        allies = [
            Character(id=1, name="Rook", class_name="fighter", hp_current=24, hp_max=24),
            Character(id=2, name="Vale", class_name="fighter", hp_current=22, hp_max=22),
        ]
        allies[0].attributes["strength"] = 18
        allies[1].attributes["strength"] = 16

        enemies = [
            Entity(id=201, name="Bandit A", level=1, hp=6, hp_current=6, hp_max=6, armour_class=10, attack_bonus=0, damage_die="d4"),
            Entity(id=202, name="Bandit B", level=1, hp=6, hp_current=6, hp_max=6, armour_class=10, attack_bonus=0, damage_die="d4"),
        ]

        def choose_action(options, _player, _enemy, _round_no, _scene):
            return "Attack" if "Attack" in options else options[0]

        result = service.fight_party_turn_based(allies, enemies, choose_action)

        self.assertTrue(result.allies_won)
        self.assertTrue(any(enemy.hp_current <= 0 for enemy in result.enemies))
        self.assertTrue(any("hits" in row.text.lower() for row in result.log))

    def test_player_can_target_ally_for_healing_spell(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(5)

        player = Character(id=1, name="Ari", class_name="cleric", hp_current=20, hp_max=20)
        player.known_spells = ["Cure Wounds"]
        player.spell_slots_current = 1
        player.attributes["dexterity"] = 18

        wounded_ally = Character(id=2, name="Silas", class_name="rogue", hp_current=3, hp_max=16)
        wounded_ally.attributes["dexterity"] = 12

        enemies = [
            Entity(id=301, name="Raider", level=1, hp=10, hp_current=10, hp_max=10, armour_class=10, attack_bonus=0, damage_die="d4"),
        ]

        def choose_action(options, _player, _enemy, _round_no, _scene):
            return ("Cast Spell", "cure-wounds") if "Cast Spell" in options else "Attack"

        def choose_target(actor, allies, enemies, round_no, scene_ctx, action):
            _ = actor
            _ = enemies
            _ = round_no
            _ = scene_ctx
            if action == "Cast Spell":
                return ("ally", 1)
            return 0

        result = service.fight_party_turn_based([player, wounded_ally], enemies, choose_action, choose_target=choose_target)

        healed_silas = next(row for row in result.allies if row.name == "Silas")
        self.assertGreater(healed_silas.hp_current, 3)

    def test_default_ai_prioritizes_healing_critical_ally(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(9)

        player = Character(id=1, name="Ari", class_name="fighter", hp_current=20, hp_max=20)
        player.attributes["dexterity"] = 10

        healer = Character(id=2, name="Elara", class_name="cleric", hp_current=12, hp_max=12)
        healer.known_spells = ["Cure Wounds"]
        healer.spell_slots_current = 2
        healer.attributes["dexterity"] = 18

        critical_ally = Character(id=3, name="Silas", class_name="rogue", hp_current=2, hp_max=12)
        critical_ally.attributes["dexterity"] = 8

        enemies = [
            Entity(id=401, name="Bandit", level=1, hp=12, hp_current=12, hp_max=12, armour_class=11, attack_bonus=0, damage_die="d4"),
        ]

        def choose_action(options, _player, _enemy, _round_no, _scene):
            return "Dodge" if "Dodge" in options else "Attack"

        result = service.fight_party_turn_based([player, healer, critical_ally], enemies, choose_action)

        healed_silas = next(row for row in result.allies if row.name == "Silas")
        self.assertGreater(healed_silas.hp_current, 2)
        self.assertTrue(any("restores" in row.text.lower() and "Silas" in row.text for row in result.log))

    def test_melee_attack_cannot_hit_rearguard_while_enemy_vanguard_alive(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(3)

        player = Character(id=1, name="Ari", class_name="fighter", hp_current=30, hp_max=30)
        player.attributes["strength"] = 18
        player.attributes["dexterity"] = 40

        enemies = [
            Entity(id=501, name="Goblin Grunt", level=1, hp=50, hp_current=50, hp_max=50, armour_class=8, attack_bonus=0, damage_die="d4"),
            Entity(id=502, name="Goblin Shaman", level=1, hp=14, hp_current=14, hp_max=14, armour_class=8, attack_bonus=0, damage_die="d4"),
        ]

        turns = {"count": 0}

        def choose_action(options, _player, _enemy, _round_no, _scene):
            turns["count"] += 1
            if turns["count"] == 1:
                return "Attack" if "Attack" in options else options[0]
            return "Flee" if "Flee" in options else "Dodge"

        def choose_target(actor, allies, enemies, round_no, scene_ctx, action):
            _ = actor
            _ = allies
            _ = round_no
            _ = scene_ctx
            if action == "Attack":
                return ("enemy", 1)
            return 0

        result = service.fight_party_turn_based([player], enemies, choose_action, choose_target=choose_target)

        front = next(row for row in result.enemies if row.name == "Goblin Grunt")
        rear = next(row for row in result.enemies if row.name == "Goblin Shaman")
        self.assertLess(front.hp_current, front.hp_max)
        self.assertEqual(rear.hp_max, rear.hp_current)

    def test_rearguard_becomes_targetable_after_vanguard_falls(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(4)

        player = Character(id=1, name="Ari", class_name="fighter", hp_current=24, hp_max=24)
        player.attributes["strength"] = 18
        player.attributes["dexterity"] = 16

        enemies = [
            Entity(id=601, name="Goblin Grunt", level=1, hp=1, hp_current=1, hp_max=1, armour_class=8, attack_bonus=0, damage_die="d4"),
            Entity(id=602, name="Goblin Shaman", level=1, hp=12, hp_current=12, hp_max=12, armour_class=8, attack_bonus=0, damage_die="d4"),
        ]

        rounds = {"count": 0}

        def choose_action(options, _player, _enemy, _round_no, _scene):
            rounds["count"] += 1
            if rounds["count"] > 2:
                return "Flee" if "Flee" in options else "Attack"
            return "Attack" if "Attack" in options else options[0]

        def choose_target(actor, allies, enemies, round_no, scene_ctx, action):
            _ = actor
            _ = allies
            _ = round_no
            _ = scene_ctx
            if action == "Attack":
                return ("enemy", 1)
            return 0

        result = service.fight_party_turn_based([player], enemies, choose_action, choose_target=choose_target)

        rear = next(row for row in result.enemies if row.name == "Goblin Shaman")
        self.assertLess(rear.hp_current, rear.hp_max)

    def test_forest_dense_cover_applies_ranged_penalty(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(12)

        player = Character(id=1, name="Ari", class_name="wizard", hp_current=20, hp_max=20)
        player.attributes["dexterity"] = 14
        player.attributes["intelligence"] = 16

        enemies = [
            Entity(id=701, name="Raider", level=1, hp=10, hp_current=10, hp_max=10, armour_class=12, attack_bonus=0, damage_die="d4"),
        ]

        def choose_action(options, _player, _enemy, _round_no, _scene):
            return "Attack" if "Attack" in options else options[0]

        result = service.fight_party_turn_based([player], enemies, choose_action, scene={"terrain": "forest"})

        self.assertTrue(any("Dense cover" in row.text for row in result.log))

    def test_mountain_dash_can_fail_and_consume_turn(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(1)

        player = Character(id=1, name="Ari", class_name="fighter", hp_current=20, hp_max=20)
        player.attributes["dexterity"] = 6

        enemies = [
            Entity(id=801, name="Raider", level=1, hp=20, hp_current=20, hp_max=20, armour_class=10, attack_bonus=0, damage_die="d4"),
        ]

        def choose_action(options, _player, _enemy, round_no, _scene):
            if round_no == 1:
                return "Dash" if "Dash" in options else "Attack"
            return "Flee" if "Flee" in options else "Dodge"

        result = service.fight_party_turn_based([player], enemies, choose_action, scene={"terrain": "mountain"})

        self.assertTrue(any("treacherous ground" in row.text for row in result.log))

    def test_swamp_heavy_armor_initiative_drag_is_applied(self) -> None:
        service = CombatService(verbosity="normal")
        service.set_seed(14)

        heavy = Character(id=1, name="Tank", class_name="fighter", hp_current=30, hp_max=30)
        heavy.flags = {"equipment": {"armor": "Chain Mail"}}
        heavy.attributes["dexterity"] = 16

        light = Character(id=2, name="Scout", class_name="rogue", hp_current=20, hp_max=20)
        light.attributes["dexterity"] = 16

        enemies = [
            Entity(id=901, name="Bandit", level=1, hp=8, hp_current=8, hp_max=8, armour_class=10, attack_bonus=0, damage_die="d4"),
        ]

        def choose_action(options, _player, _enemy, _round_no, _scene):
            return "Flee" if "Flee" in options else "Dodge"

        result = service.fight_party_turn_based([heavy, light], enemies, choose_action, scene={"terrain": "swamp"})

        queue_line = next((row.text for row in result.log if row.text.startswith("Initiative queue:")), "")
        self.assertIn("Tank", queue_line)
        self.assertIn("Scout", queue_line)
        self.assertTrue(queue_line.index("Scout") < queue_line.index("Tank"))


if __name__ == "__main__":
    unittest.main()
